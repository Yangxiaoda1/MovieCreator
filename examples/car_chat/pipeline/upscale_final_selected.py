#!/usr/bin/env python3
"""Upscale the selected picture lock shot-by-shot with SeedVR2 and rebuild 4K masters.

Shot-level processing avoids loading the complete 230-second 1080p film into
SeedVR2 at once. Jobs are resumable and distributed over multiple ComfyUI
servers. The final unified dialogue/SFX/music mix is muxed only after the
upscaled picture lock is assembled; subtitles are burned at native 4K.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AIMOVIE = ROOT.parent
OUT = ROOT / "output"
SELECTED = OUT / "video_raw" / "selected"
UPSCALED = OUT / "resolution" / "seedvr2_2x"
FINAL = OUT / "final"
OTHERS = OUT / "others"
MANIFEST = OUT / "resolution" / "seedvr2_2x_manifest.json"
COMFY = AIMOVIE / "ComfyUI"
COMFY_OUTPUT = AIMOVIE / "output"


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def probe(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration,size:"
                "stream=index,codec_name,codec_type,width,height,r_frame_rate,"
                "sample_rate,channels"
            ),
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


def load_upscaler():
    source = ROOT / "aifilm_booklet" / "tools" / "seedvr2_upscale.py"
    spec = importlib.util.spec_from_file_location("seedvr2_upscale", source)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def valid_existing(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100_000:
        return False
    try:
        info = probe(path)
        video = next(
            stream
            for stream in info["streams"]
            if stream.get("codec_type") == "video"
        )
        return int(video.get("width", 0)) == 3840 and int(video.get("height", 0)) == 2160
    except Exception:
        return False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--servers", nargs="+", default=["http://127.0.0.1:8189", "http://127.0.0.1:8190", "http://127.0.0.1:8192"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    upscaler = load_upscaler()
    plan = json.loads((OTHERS / "shot_plan.json").read_text(encoding="utf-8"))
    shots = plan["shots"]
    UPSCALED.mkdir(parents=True, exist_ok=True)
    state = {
        "project": "车上聊天",
        "engine": "SeedVR2 3B",
        "scale": 2.0,
        "resolution": "3840x2160",
        "started_at": now(),
        "updated_at": now(),
        "shots": {},
    }
    if MANIFEST.exists():
        try:
            state["shots"].update(json.loads(MANIFEST.read_text(encoding="utf-8")).get("shots", {}))
        except Exception:
            pass

    jobs = []
    for shot in shots:
        source = SELECTED / f"{shot['id']}.mp4"
        target = UPSCALED / f"{shot['id']}.mp4"
        prior = state["shots"].get(shot["id"], {})
        source_digest = sha256(source)
        reusable = (
            not args.force
            and valid_existing(target)
            and prior.get("status") == "completed"
            and prior.get("source_sha256") == source_digest
        )
        if reusable:
            state["shots"][shot["id"]] = {
                "status": "completed",
                "resumed": True,
                "source": str(source.relative_to(ROOT)),
                "source_sha256": source_digest,
                "output": str(target.relative_to(ROOT)),
                "sha256": sha256(target),
                "probe": probe(target),
            }
        else:
            jobs.append((shot, source, target))

    lock = threading.Lock()
    queue = jobs.copy()

    def worker(server: str):
        while True:
            with lock:
                if not queue:
                    return
                shot, source, target = queue.pop(0)
            sid = shot["id"]
            print(f"[{now()}] {sid} start on {server}", flush=True)
            try:
                generated = upscaler.upscale_video(
                    video=source,
                    server=server,
                    comfy_dir=COMFY,
                    output_dir=COMFY_OUTPUT,
                    output_prefix=f"car_chat_interaction9/seedvr2_2x/{sid}",
                    input_namespace="car_chat_interaction9/seedvr2_inputs",
                    scale=2.0,
                    seed=202609260000 + int(sid.split("_")[1]),
                    color_correction="lab",
                    split_latent=True,
                    temporal_overlap=2,
                    frames_per_chunk=33,
                    model_name="seedvr2_3b_int8_convrot.safetensors",
                    vae_name="seedvr2_ema_vae_fp16.safetensors",
                    timeout_hours=4,
                    graph_path=OUT / "others" / "seedvr2_workflows" / f"{sid}.json",
                )
                shutil.copy2(generated, target)
                if not valid_existing(target):
                    raise RuntimeError(f"invalid 4K output: {target}")
                record = {
                    "status": "completed",
                    "server": server,
                    "source": str(source.relative_to(ROOT)),
                    "source_sha256": sha256(source),
                    "output": str(target.relative_to(ROOT)),
                    "sha256": sha256(target),
                    "probe": probe(target),
                    "completed_at": now(),
                }
                print(f"[{now()}] {sid} completed: {target}", flush=True)
            except Exception as error:
                record = {
                    "status": "failed",
                    "server": server,
                    "source": str(source.relative_to(ROOT)),
                    "error": repr(error),
                    "completed_at": now(),
                }
                print(f"[{now()}] {sid} FAILED: {error!r}", flush=True)
            with lock:
                state["shots"][sid] = record
                state["updated_at"] = now()
                write_json(MANIFEST, state)

    with ThreadPoolExecutor(max_workers=len(args.servers)) as pool:
        futures = [pool.submit(worker, server) for server in args.servers]
        for future in as_completed(futures):
            future.result()

    failed = [
        sid for sid, record in state["shots"].items() if record.get("status") != "completed"
    ]
    if failed:
        state["status"] = "failed"
        state["failed"] = failed
        write_json(MANIFEST, state)
        raise SystemExit(f"SeedVR2 failed shots: {failed}")

    concat_path = OTHERS / "picture_lock_4k_concat.txt"
    concat_path.write_text(
        "\n".join(
            "file '" + (UPSCALED / f"{shot['id']}.mp4").as_posix() + "'"
            for shot in shots
        )
        + "\n",
        encoding="utf-8",
    )
    picture_4k = OUT / "resolution" / "picture_lock_4k.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-an",
            "-c:v",
            "copy",
            str(picture_4k),
        ]
    )

    mix = OUT / "audio" / "final_mix.wav"
    srt = OTHERS / "movie.zh-CN.srt"
    no_sub = FINAL / "movie_final_4k_no_subtitles.mp4"
    final = FINAL / "movie_final_4k.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(picture_4k),
            "-i",
            str(mix),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(no_sub),
        ]
    )
    escaped = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    fonts_dir = str(OUT / "fonts").replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(no_sub),
            "-vf",
            (
                f"subtitles='{escaped}':fontsdir='{fonts_dir}':"
                "force_style='FontName=Noto Sans CJK SC,FontSize=14,"
                "Outline=1.2,Shadow=0,Alignment=2,MarginV=12'"
            ),
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            str(final),
        ]
    )
    for path in (picture_4k, no_sub, final):
        run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"])

    state.update(
        {
            "status": "completed",
            "updated_at": now(),
            "picture_lock_4k": {
                "path": str(picture_4k.relative_to(ROOT)),
                "sha256": sha256(picture_4k),
                "probe": probe(picture_4k),
            },
            "deliverables": {
                "movie_final_4k": {
                    "path": str(final.relative_to(ROOT)),
                    "sha256": sha256(final),
                    "probe": probe(final),
                },
                "movie_final_4k_no_subtitles": {
                    "path": str(no_sub.relative_to(ROOT)),
                    "sha256": sha256(no_sub),
                    "probe": probe(no_sub),
                },
            },
        }
    )
    write_json(MANIFEST, state)

    final_manifest_path = FINAL / "manifest.json"
    final_manifest = json.loads(final_manifest_path.read_text(encoding="utf-8"))
    final_manifest["upscale"] = "SeedVR2 3B 2x, shot-level temporal processing"
    final_manifest["deliverables"].update(state["deliverables"])
    final_manifest["created_at"] = now()
    write_json(final_manifest_path, final_manifest)
    print(json.dumps(state["deliverables"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
