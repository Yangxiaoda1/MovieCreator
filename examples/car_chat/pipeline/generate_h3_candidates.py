#!/usr/bin/env python3
"""Generate two MiniMax H3 Turbo Ref2VA candidates for each locked dialogue shot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import threading
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AIMOVIE = ROOT.parent
COMFY_INPUT = AIMOVIE / "ComfyUI" / "input" / "car_chat_interaction9"
COMFY_OUTPUT = AIMOVIE / "output"
PLAN_PATH = ROOT / "output" / "others" / "shot_plan_h3.json"
DEST = ROOT / "output" / "video_raw" / "candidates"
MANIFEST_PATH = ROOT / "output" / "others" / "h3_candidate_manifest.json"
LOG_PATH = ROOT / "output" / "others" / "h3_candidate_progress.log"
PORTS = [8188, 8189, 8190]

MODEL = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
CLIP = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"
AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"
LORA = "minimax_h3_turbo_v4_step600_ema.safetensors"


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def log(message: str) -> None:
    line = f"[{now()}] {message}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def request_json(url: str, payload=None, timeout: int = 60):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def media_probe(path: Path) -> dict:
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout)


def stage_input(source: Path, name: str) -> str:
    COMFY_INPUT.mkdir(parents=True, exist_ok=True)
    dst = COMFY_INPUT / name
    if not dst.exists() or sha256(dst) != sha256(source):
        shutil.copy2(source, dst)
    return f"car_chat_interaction9/{name}"


def speaker_files(shot: dict) -> tuple[Path, Path]:
    speaker = shot["speaker"]
    identity = {
        "中国男1": ROOT / "input/roles/中国男1/中国男1_正面.png",
        "中国女2": ROOT / "input/roles/中国女2/中国女2_正面.png",
        "警察探长": ROOT / "input/roles/警察探长/警察探长_脸部近景.png",
    }[speaker]
    voice = ROOT / shot["reference_audio_assets"][0]["path"]
    return identity, voice


def frame_count(duration: float) -> int:
    base = max(5, round(duration * 24))
    return base + (5 - (base % 17)) % 17


def build_graph(shot: dict, candidate: int, seed: int) -> dict:
    sid = shot["id"]
    identity, voice = speaker_files(shot)
    candidate_reference = shot.get("candidate_reference_assets", {}).get(
        f"cand{candidate:02d}"
    )
    primary_reference = next(
        (
            ROOT / item["path"]
            for item in shot.get("reference_assets", [])
            if item.get("role") in {"action", "start_frame", "reference"}
            and (ROOT / item["path"]).is_file()
        ),
        ROOT / f"output/images_prepare/shots/{sid}_reference.png",
    )
    if candidate_reference and (ROOT / candidate_reference).is_file():
        primary_reference = ROOT / candidate_reference
    staged = {
        "shot": stage_input(primary_reference, primary_reference.name),
        "identity": stage_input(identity, f"{shot['speaker']}_identity{identity.suffix}"),
        "scene": stage_input(
            ROOT / "input/scenes/装甲警车/装甲警车_车内内饰_三人座位.png",
            "armored_police_vehicle_interior.png",
        ),
    }
    if shot.get("use_reference_audio", True):
        staged["voice"] = stage_input(
            voice, f"{shot['speaker']}_voice{voice.suffix}"
        )
    if shot.get("use_full_identity_refs"):
        staged.update(
            {
                "male": stage_input(
                    ROOT / "input/roles/中国男1/中国男1_正面.png",
                    "中国男1_identity.png",
                ),
                "female": stage_input(
                    ROOT / "input/roles/中国女2/中国女2_正面.png",
                    "中国女2_identity.png",
                ),
                "captain": stage_input(
                    ROOT / "input/roles/警察探长/警察探长_脸部近景.png",
                    "警察探长_identity.png",
                ),
            }
        )
    prefix = f"car_chat_interaction9/candidates/episode{shot['episode']:02d}/{sid}_cand{candidate:02d}"
    variant_key = f"cand{candidate:02d}"
    variant_prompt = shot.get("candidate_prompt_variants", {}).get(
        variant_key, shot["video_prompt"]
    )
    prompt = (
        "最高优先级视觉约束：视频第1帧必须严格继承 Picture 1 的构图、车内空间、"
        "三人座位、脸、发型和服装；全镜保持这些外观。中国男1只能穿纯黑色无图案圆领短袖，"
        "不得穿警服、制服、衬衫或带肩章服装；中国女2只能穿黑色皮夹克与白色背心；"
        "警察探长只能穿黑色圆领警务训练服与深色战术裤。"
        "车外为夜间或昏暗城市流光，不得变成白天普通民用车。"
        "画面内不得出现任何可读字母、POLICE字样、徽章文字、字幕、标牌、水印或logo。"
        + variant_prompt
    )
    graph = {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {"unet_name": MODEL, "weight_dtype": "default"},
        },
        "2": {
            "class_type": "CLIPLoader",
            "inputs": {"clip_name": CLIP, "type": "minimax", "device": "default"},
        },
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VIDEO_VAE}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": AUDIO_VAE}},
        "5": {
            "class_type": "MiniMaxH3TurboLoRA",
            "inputs": {
                "model": ["1", 0],
                "lora_name": LORA,
                "strength": 1.0,
                "low_vram": False,
            },
        },
        "10": {"class_type": "LoadImage", "inputs": {"image": staged["shot"]}},
        "11": {"class_type": "LoadImage", "inputs": {"image": staged["identity"]}},
        "12": {"class_type": "LoadImage", "inputs": {"image": staged["scene"]}},
        "20": {
            "class_type": "MiniMaxH3ReferenceToVideo",
            "inputs": {
                "clip": ["2", 0],
                "vae": ["3", 0],
                "audio_vae": ["4", 0],
                "prompt": prompt,
                "width": 1024,
                "height": 576,
                "length": frame_count(shot["duration_sec"]),
                "ref_image_size": "match",
                "ref_images": {},
                "ref_audios": (
                    {"ref_audio_1": ["13", 0]}
                    if shot.get("use_reference_audio", True)
                    else {}
                ),
            },
        },
        "21": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "22": {
            "class_type": "BasicGuider",
            "inputs": {"model": ["5", 0], "conditioning": ["20", 0]},
        },
        "23": {"class_type": "MiniMaxH3TurboSampler", "inputs": {}},
        "24": {
            "class_type": "BasicScheduler",
            "inputs": {"model": ["5", 0], "scheduler": "simple", "steps": 8, "denoise": 1.0},
        },
        "25": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": ["21", 0],
                "guider": ["22", 0],
                "sampler": ["23", 0],
                "sigmas": ["24", 0],
                "latent_image": ["20", 1],
            },
        },
        "26": {"class_type": "VAEDecode", "inputs": {"samples": ["25", 0], "vae": ["3", 0]}},
        "27": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["25", 0], "vae": ["4", 0]}},
        "28": {
            "class_type": "CreateVideo",
            "inputs": {"images": ["26", 0], "fps": 24.0, "audio": ["27", 0]},
        },
        "29": {
            "class_type": "SaveVideo",
            "inputs": {"video": ["28", 0], "filename_prefix": prefix, "format": "auto"},
        },
    }
    if shot.get("use_reference_audio", True):
        graph["13"] = {
            "class_type": "LoadAudio",
            "inputs": {"audio": staged["voice"]},
        }
    if shot.get("use_full_identity_refs"):
        graph.update(
            {
                "14": {"class_type": "LoadImage", "inputs": {"image": staged["male"]}},
                "15": {"class_type": "LoadImage", "inputs": {"image": staged["female"]}},
                "16": {"class_type": "LoadImage", "inputs": {"image": staged["captain"]}},
            }
        )
        graph["20"]["inputs"]["ref_images"] = {
            "ref_image_1": ["10", 0],
            "ref_image_2": ["14", 0],
            "ref_image_3": ["15", 0],
            "ref_image_4": ["16", 0],
            "ref_image_5": ["12", 0],
        }
    else:
        graph["20"]["inputs"]["ref_images"] = {
            "ref_image_1": ["10", 0],
            "ref_image_2": ["11", 0],
            "ref_image_3": ["12", 0],
        }

    if shot.get("use_first_frame_guide", True):
        graph["30"] = {
            "class_type": "MiniMaxH3AddGuide",
            "inputs": {
                "positive": ["20", 0],
                "latent": ["20", 1],
                "frame_idx": 0,
                "vae": ["3", 0],
                "image": ["10", 0],
            },
        }
        graph["22"]["inputs"]["conditioning"] = ["30", 0]
    return graph


def resolve_history_output(item: dict) -> Path:
    candidates = []
    for node in item.get("outputs", {}).values():
        if not isinstance(node, dict):
            continue
        for key in ("videos", "video", "images", "audio"):
            values = node.get(key, [])
            if isinstance(values, dict):
                values = [values]
            for result in values:
                if not isinstance(result, dict) or not result.get("filename"):
                    continue
                candidates.append(
                    COMFY_OUTPUT / result.get("subfolder", "") / result["filename"]
                )
    videos = [x for x in candidates if x.suffix.lower() in {".mp4", ".webm", ".mkv"}]
    if not videos:
        raise RuntimeError(f"Comfy history contained no video output: {candidates}")
    return videos[-1]


def run_job(port: int, shot: dict, candidate: int, seed: int) -> dict:
    sid = shot["id"]
    target_dir = DEST / f"episode{shot['episode']:02d}"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{sid}_cand{candidate:02d}.mp4"
    if target.exists() and target.stat().st_size > 100_000:
        try:
            probe = media_probe(target)
            subprocess.run(
                ["ffmpeg", "-v", "error", "-i", str(target), "-f", "null", "-"],
                check=True,
            )
            return {
                "shot_id": sid,
                "episode": shot["episode"],
                "candidate": candidate,
                "seed": seed,
                "status": "completed",
                "resumed": True,
                "output": str(target.relative_to(ROOT)),
                "sha256": sha256(target),
                "probe": probe,
            }
        except Exception:
            pass

    graph = build_graph(shot, candidate, seed)
    workflow_path = (
        ROOT
        / "output"
        / "others"
        / "h3_workflows"
        / f"{sid}_cand{candidate:02d}.json"
    )
    atomic_json(workflow_path, graph)
    base = f"http://127.0.0.1:{port}"
    start = time.monotonic()
    response = request_json(
        base + "/prompt",
        {"prompt": graph, "client_id": f"car-chat-{uuid.uuid4()}"},
        timeout=120,
    )
    prompt_id = response["prompt_id"]
    log(
        f"[episode {shot['episode']:02d}][{sid}][candidate {candidate}/2] "
        f"submitted port={port} seed={seed} prompt_id={prompt_id} output={target}"
    )
    while True:
        history = request_json(base + f"/history/{prompt_id}", timeout=120)
        if prompt_id in history:
            item = history[prompt_id]
            status = item.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(json.dumps(status, ensure_ascii=False))
            if status.get("completed") is True:
                source = resolve_history_output(item)
                shutil.copy2(source, target)
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-i", str(target), "-f", "null", "-"],
                    check=True,
                )
                probe = media_probe(target)
                record = {
                    "shot_id": sid,
                    "episode": shot["episode"],
                    "candidate": candidate,
                    "seed": seed,
                    "status": "completed",
                    "port": port,
                    "prompt_id": prompt_id,
                    "elapsed_sec": round(time.monotonic() - start, 2),
                    "source_output": str(source),
                    "output": str(target.relative_to(ROOT)),
                    "sha256": sha256(target),
                    "workflow": str(workflow_path.relative_to(ROOT)),
                    "prompt": graph["20"]["inputs"]["prompt"],
                    "prompt_variant": f"cand{candidate:02d}",
                    "prompt_variant_source": (
                        "candidate_prompt_variants"
                        if shot.get("candidate_prompt_variants", {}).get(
                            f"cand{candidate:02d}"
                        )
                        else "video_prompt"
                    ),
                    "reference_assets": shot["reference_assets"],
                    "reference_audio_assets": shot["reference_audio_assets"],
                    "resolution_requested": "1024x576",
                    "frames_requested": frame_count(shot["duration_sec"]),
                    "fps_requested": 24,
                    "steps": 8,
                    "probe": probe,
                }
                log(
                    f"[episode {shot['episode']:02d}][{sid}][candidate {candidate}/2] "
                    f"completed elapsed={record['elapsed_sec']}s output={target}"
                )
                return record
        elapsed = int(time.monotonic() - start)
        if elapsed % 60 < 10:
            log(
                f"[episode {shot['episode']:02d}][{sid}][candidate {candidate}/2] "
                f"running port={port} elapsed={elapsed}s operation_steps=8"
            )
        if elapsed > 10800:
            raise TimeoutError(f"{sid} candidate {candidate} exceeded 3 hours")
        time.sleep(10)


def worker(port: int, queue: list[tuple[dict, int, int]], manifest: dict, lock: threading.Lock):
    while True:
        with lock:
            if not queue:
                return
            shot, candidate, seed = queue.pop(0)
        key = f"{shot['id']}_cand{candidate:02d}"
        try:
            record = run_job(port, shot, candidate, seed)
        except Exception as exc:
            record = {
                "shot_id": shot["id"],
                "episode": shot["episode"],
                "candidate": candidate,
                "seed": seed,
                "status": "failed",
                "port": port,
                "error": repr(exc),
            }
            log(f"[{key}] FAILED port={port} error={exc!r}")
        with lock:
            manifest["jobs"][key] = record
            manifest["updated_at"] = now()
            atomic_json(MANIFEST_PATH, manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", nargs="*", help="Optional shot ids")
    parser.add_argument("--candidate", type=int, choices=[1, 2])
    parser.add_argument(
        "--job",
        action="append",
        default=[],
        help="Exact shot/candidate job, repeatable, e.g. shot_016:1",
    )
    parser.add_argument("--ports", nargs="*", type=int, default=PORTS)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--seed-offset", type=int, default=0)
    args = parser.parse_args()
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    shots = plan["shots"]
    if args.shots:
        wanted = set(args.shots)
        shots = [s for s in shots if s["id"] in wanted]
    queue = []
    if args.job:
        by_id = {shot["id"]: shot for shot in shots}
        exact_jobs = []
        for raw in args.job:
            shot_id, separator, candidate_raw = raw.partition(":")
            if not separator or shot_id not in by_id:
                raise ValueError(f"Invalid --job {raw!r}; expected known_shot_id:1|2")
            candidate = int(candidate_raw)
            if candidate not in (1, 2):
                raise ValueError(f"Invalid candidate in --job {raw!r}")
            exact_jobs.append((by_id[shot_id], candidate))
    else:
        candidates = [args.candidate] if args.candidate else [1, 2]
        exact_jobs = [
            (shot, candidate)
            for shot in shots
            for candidate in candidates
        ]
    for shot, candidate in exact_jobs:
        seed = (
            202609250000
            + int(shot["id"].split("_")[1]) * 10
            + candidate
            + args.seed_offset
        )
        queue.append((shot, candidate, seed))
    if args.force:
        for shot, candidate, _seed in queue:
            target = (
                DEST
                / f"episode{shot['episode']:02d}"
                / f"{shot['id']}_cand{candidate:02d}.mp4"
            )
            if target.exists():
                archived = (
                    ROOT
                    / "output"
                    / "video_raw"
                    / "rejected_preflight"
                    / f"{shot['id']}_cand{candidate:02d}_{int(time.time())}.mp4"
                )
                archived.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, archived)
                log(f"archived previous output {target} -> {archived}")

    manifest = {
        "project": "车上聊天",
        "engine": "MiniMax H3 Turbo",
        "model": MODEL,
        "clip": CLIP,
        "video_vae": VIDEO_VAE,
        "audio_vae": AUDIO_VAE,
        "lora": LORA,
        "steps": 8,
        "resolution": "1024x576",
        "candidate_policy": (
            "same locked story target, reference package, frame count and resolution; "
            "shots with candidate_prompt_variants intentionally use two camera/performance "
            "prompt variants, and seed also differs"
        ),
        "started_at": now(),
        "updated_at": now(),
        "jobs": {},
    }
    if MANIFEST_PATH.exists():
        try:
            old = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            manifest["jobs"].update(old.get("jobs", {}))
        except Exception:
            pass
    lock = threading.Lock()
    log(f"starting {len(queue)} formal candidate jobs on ports={args.ports}")
    with ThreadPoolExecutor(max_workers=len(args.ports)) as pool:
        futures = [pool.submit(worker, port, queue, manifest, lock) for port in args.ports]
        for future in as_completed(futures):
            future.result()
    failed = [v for v in manifest["jobs"].values() if v.get("status") == "failed"]
    completed = [v for v in manifest["jobs"].values() if v.get("status") == "completed"]
    manifest["status"] = "failed" if failed else "completed"
    manifest["completed_count"] = len(completed)
    manifest["failed_count"] = len(failed)
    manifest["updated_at"] = now()
    atomic_json(MANIFEST_PATH, manifest)
    log(f"all workers ended completed={len(completed)} failed={len(failed)}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
