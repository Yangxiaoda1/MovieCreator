#!/usr/bin/env python3
"""Upscale one or more videos with ComfyUI's native SeedVR2 workflow."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


# <WORKSPACE>/<PROJECT_ROOT>/aifilm_booklet/tools/seedvr2_upscale.py
WORKSPACE = Path(
    os.environ.get("AIFILM_WORKSPACE", Path(__file__).resolve().parents[3])
)
DEFAULT_SERVER = "http://127.0.0.1:8188"
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov"}


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI returned HTTP {error.code}: {body}") from error


def wait_for_prompt(server: str, prompt_id: str, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        history = request_json(f"{server}/history/{prompt_id}")
        if prompt_id in history:
            result = history[prompt_id]
            status = result.get("status", {})
            if status.get("status_str") == "error" or status.get("completed") is False:
                messages = status.get("messages", status)
                raise RuntimeError(json.dumps(messages, ensure_ascii=False, indent=2))
            return result
        time.sleep(5)
    raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")


def find_saved_video(history: dict, node_id: str = "15") -> dict:
    candidates = []

    def walk(value):
        if isinstance(value, dict):
            filename = value.get("filename")
            if filename and Path(filename).suffix.lower() in VIDEO_EXTENSIONS:
                candidates.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(history.get("outputs", {}).get(node_id, {}))
    if not candidates:
        walk(history.get("outputs", {}))
    if not candidates:
        raise RuntimeError("SeedVR2 completed but no saved video was found")
    return candidates[-1]


def copy_to_input(source: Path, input_dir: Path, name: str) -> str:
    destination = input_dir / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    return name


def build_seedvr2_prompt(
    *,
    input_name: str,
    output_prefix: str,
    scale: float,
    seed: int,
    color_correction: str,
    split_latent: bool,
    temporal_overlap: int,
    frames_per_chunk: int | None,
    model_name: str,
    vae_name: str,
) -> dict:
    encoded = ["7", 0]
    sampled = ["10", 0]
    graph = {
        "1": {
            "class_type": "LoadVideo",
            "inputs": {"file": input_name},
        },
        "2": {
            "class_type": "GetVideoComponents",
            "inputs": {"video": ["1", 0]},
        },
        "3": {
            "class_type": "ResizeImageMaskNode",
            "inputs": {
                "input": ["2", 0],
                "resize_type": "scale by multiplier",
                "resize_type.multiplier": scale,
                "scale_method": "lanczos",
            },
        },
        "4": {
            "class_type": "SeedVR2Preprocess",
            "inputs": {"resized_images": ["3", 0]},
        },
        "5": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": vae_name},
        },
        "6": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": model_name,
                "weight_dtype": "default",
            },
        },
        "7": {
            "class_type": "VAEEncodeTiled",
            "inputs": {
                "pixels": ["4", 0],
                "vae": ["5", 0],
                "tile_size": 512,
                "overlap": 128,
                "temporal_size": 64,
                "temporal_overlap": 8,
            },
        },
        "9": {
            "class_type": "SeedVR2Conditioning",
            "inputs": {
                "model": ["6", 0],
                "vae_conditioning": encoded,
            },
        },
        "10": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["6", 0],
                "seed": seed,
                "steps": 1,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": ["9", 0],
                "negative": ["9", 1],
                "latent_image": encoded,
                "denoise": 1.0,
            },
        },
        "12": {
            "class_type": "VAEDecodeTiled",
            "inputs": {
                "samples": sampled,
                "vae": ["5", 0],
                "tile_size": 512,
                "overlap": 128,
                "temporal_size": 64,
                "temporal_overlap": 8,
            },
        },
        "13": {
            "class_type": "SeedVR2PostProcessing",
            "inputs": {
                "images": ["12", 0],
                "original_resized_images": ["3", 0],
                "color_correction_method": color_correction,
            },
        },
        "14": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": ["13", 0],
                "audio": ["2", 1],
                "fps": ["2", 2],
                "bit_depth": 8,
                "color_space": "sRGB",
            },
        },
        "15": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": ["14", 0],
                "filename_prefix": output_prefix,
                "format": "mp4",
                "format.codec": "h264",
                "format.codec.encoding": "re-encode",
                "format.codec.encoding.crf": 17.0,
            },
        },
    }
    if split_latent:
        graph["8"] = {
            "class_type": "SeedVR2TemporalChunk",
            "inputs": {
                "latent": ["7", 0],
                "temporal_overlap": temporal_overlap,
                "chunking_mode": "manual" if frames_per_chunk is not None else "auto",
            },
        }
        if frames_per_chunk is not None:
            # ComfyUI DynamicCombo API inputs are flattened with the parent
            # widget name, matching the schema path generated by _io.py.
            graph["8"]["inputs"]["chunking_mode.frames_per_chunk"] = frames_per_chunk
        graph["9"]["inputs"]["vae_conditioning"] = ["8", 0]
        graph["10"]["inputs"]["latent_image"] = ["8", 0]
        graph["11"] = {
            "class_type": "SeedVR2TemporalMerge",
            "inputs": {
                "latents": ["10", 0],
                "temporal_overlap": ["8", 1],
            },
        }
        graph["12"]["inputs"]["samples"] = ["11", 0]
    return graph


def upscale_video(
    *,
    video: Path,
    server: str,
    comfy_dir: Path,
    output_dir: Path,
    output_prefix: str,
    input_namespace: str,
    scale: float = 2.0,
    seed: int = 1,
    color_correction: str = "lab",
    split_latent: bool = True,
    temporal_overlap: int = 2,
    frames_per_chunk: int | None = None,
    model_name: str = "seedvr2_3b_int8_convrot.safetensors",
    vae_name: str = "seedvr2_ema_vae_fp16.safetensors",
    timeout_hours: float = 6,
    graph_path: Path | None = None,
) -> Path:
    video = video.expanduser().resolve()
    if not video.is_file():
        raise FileNotFoundError(video)
    input_name = f"{input_namespace}/{video.name}"
    copy_to_input(video, comfy_dir.resolve() / "input", input_name)
    graph = build_seedvr2_prompt(
        input_name=input_name,
        output_prefix=output_prefix,
        scale=scale,
        seed=seed,
        color_correction=color_correction,
        split_latent=split_latent,
        temporal_overlap=temporal_overlap,
        frames_per_chunk=frames_per_chunk,
        model_name=model_name,
        vae_name=vae_name,
    )
    if graph_path is not None:
        graph_path.parent.mkdir(parents=True, exist_ok=True)
        graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2))

    response = request_json(
        f"{server}/prompt",
        {"prompt": graph, "client_id": str(uuid.uuid4())},
    )
    history = wait_for_prompt(
        server,
        response["prompt_id"],
        timeout_hours * 3600,
    )
    item = find_saved_video(history)
    result = output_dir.resolve() / item.get("subfolder", "") / item["filename"]
    if not result.is_file():
        raise FileNotFoundError(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("videos", nargs="+", type=Path)
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument(
        "--comfy-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "ComfyUI",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "output",
    )
    parser.add_argument("--prefix", default="seedvr2")
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument(
        "--color-correction",
        choices=["lab", "wavelet", "adain", "none"],
        default="lab",
    )
    parser.add_argument("--no-split-latent", action="store_true")
    parser.add_argument("--temporal-overlap", type=int, default=2)
    parser.add_argument(
        "--frames-per-chunk",
        type=int,
        help="Use manual temporal chunks (must be 4n+1, e.g. 33) instead of auto sizing",
    )
    parser.add_argument("--model", default="seedvr2_3b_int8_convrot.safetensors")
    parser.add_argument("--vae", default="seedvr2_ema_vae_fp16.safetensors")
    parser.add_argument("--timeout-hours", type=float, default=6)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not 0.01 <= args.scale <= 8:
        raise ValueError("--scale must be between 0.01 and 8")
    input_dir = args.comfy_dir.resolve() / "input"
    output_dir = args.output_dir.resolve()
    run_id = time.strftime("%Y%m%d_%H%M%S")
    graph_dir = WORKSPACE / "runs" / f"seedvr2_{run_id}"
    graph_dir.mkdir(parents=True, exist_ok=True)

    if not args.dry_run:
        stats = request_json(f"{args.server}/system_stats")
        print(f"Connected to ComfyUI {stats.get('system', {}).get('comfyui_version', '?')}")

    results = []
    for index, video in enumerate(args.videos):
        video = video.expanduser().resolve()
        if not video.is_file():
            raise FileNotFoundError(video)
        input_name = f"aimovie_upscale/{run_id}/{index:03d}_{video.name}"
        graph = build_seedvr2_prompt(
            input_name=input_name,
            output_prefix=f"aimovie/{args.prefix}_{run_id}/{index:03d}_{video.stem}",
            scale=args.scale,
            seed=args.seed + index,
            color_correction=args.color_correction,
            split_latent=not args.no_split_latent,
            temporal_overlap=args.temporal_overlap,
            frames_per_chunk=args.frames_per_chunk,
            model_name=args.model,
            vae_name=args.vae,
        )
        graph_path = graph_dir / f"{index:03d}_{video.stem}.json"
        graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2))
        print(f"[{index + 1}/{len(args.videos)}] {video.name} -> SeedVR2 x{args.scale:g}")
        if args.dry_run:
            continue

        result = upscale_video(
            video=video,
            server=args.server,
            comfy_dir=args.comfy_dir,
            output_dir=output_dir,
            output_prefix=f"aimovie/{args.prefix}_{run_id}/{index:03d}_{video.stem}",
            input_namespace=f"aimovie_upscale/{run_id}",
            scale=args.scale,
            seed=args.seed + index,
            color_correction=args.color_correction,
            split_latent=not args.no_split_latent,
            temporal_overlap=args.temporal_overlap,
            frames_per_chunk=args.frames_per_chunk,
            model_name=args.model,
            vae_name=args.vae,
            timeout_hours=args.timeout_hours,
            graph_path=graph_path,
        )
        results.append(result)
        print(f"  saved: {result}")

    if args.dry_run:
        print(f"Wrote {len(args.videos)} SeedVR2 API graph(s) to {graph_dir}")
    else:
        manifest = {"source": [str(v.resolve()) for v in args.videos], "outputs": [str(v) for v in results]}
        (graph_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
