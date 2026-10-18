#!/usr/bin/env python3
"""Generate/organize the S05 static asset package without touching user inputs."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
IMAGES = OUT / "images_prepare"
OTHERS = OUT / "others"
GATEWAY = ROOT / "aifilm_booklet" / "tools" / "gpt_image_gateway.py"
SCENE = ROOT / "input" / "scenes" / "装甲警车" / "装甲警车_车内内饰_三人座位.png"
PROVIDERS = ["azure_openai", "naci_default", "openai"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def make_face_crop(src: Path, dst: Path) -> None:
    img = Image.open(src).convert("RGB")
    w, h = img.size
    # Input front references are full-body portraits. Keep head and shoulders.
    left = int(w * 0.22)
    right = int(w * 0.78)
    top = int(h * 0.03)
    bottom = int(h * 0.43)
    crop = img.crop((left, top, right, bottom))
    crop = crop.resize((1024, 1024), Image.Resampling.LANCZOS)
    dst.parent.mkdir(parents=True, exist_ok=True)
    crop.save(dst, format="PNG")


def run_image_job(shot: dict, index: int) -> dict:
    sid = shot["id"]
    dst = IMAGES / "shots" / f"{sid}_reference.png"
    prompt_file = OTHERS / "image_prompts" / f"{sid}.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(shot["image_prompt"], encoding="utf-8")
    if dst.exists() and dst.stat().st_size > 10_000:
        return {"shot_id": sid, "path": str(dst.relative_to(ROOT)), "resumed": True}

    speaker = shot["speaker"]
    identity = {
        "中国男1": ROOT / "input/roles/中国男1/中国男1_正面.png",
        "中国女2": ROOT / "input/roles/中国女2/中国女2_正面.png",
        "警察探长": ROOT / "input/roles/警察探长/警察探长_脸部近景.png",
    }[speaker]
    errors = []
    for attempt in range(5):
        provider = PROVIDERS[(index + attempt) % len(PROVIDERS)]
        env = os.environ.copy()
        env["AIMOVIE_IMAGE_MODEL"] = "gpt-image-2"
        env["AIMOVIE_IMAGE_PROVIDER"] = provider
        cmd = [
            "python",
            str(GATEWAY),
            "--edit",
            "--image",
            str(SCENE),
            "--image",
            str(identity),
            "--prompt-file",
            str(prompt_file),
            "--out",
            str(dst),
            "--size",
            "1536x864",
            "--quality",
            "medium",
            "--timeout",
            "900",
        ]
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if proc.returncode == 0 and dst.exists() and dst.stat().st_size > 10_000:
            return {
                "shot_id": sid,
                "path": str(dst.relative_to(ROOT)),
                "provider": provider,
                "attempt": attempt + 1,
                "inputs": [
                    {"path": str(SCENE.relative_to(ROOT)), "role": "scene_and_group_layout"},
                    {"path": str(identity.relative_to(ROOT)), "role": f"{speaker}_identity"},
                ],
                "stdout": proc.stdout[-1000:],
            }
        errors.append({"provider": provider, "stderr": proc.stderr[-1500:]})
        time.sleep(3)
    return {"shot_id": sid, "path": str(dst.relative_to(ROOT)), "error": errors}


def main() -> None:
    (IMAGES / "characters").mkdir(parents=True, exist_ok=True)
    (IMAGES / "scenes").mkdir(parents=True, exist_ok=True)
    (IMAGES / "props").mkdir(parents=True, exist_ok=True)
    (IMAGES / "shots").mkdir(parents=True, exist_ok=True)

    # Organize deterministic derived assets; original input files remain unchanged.
    make_face_crop(
        ROOT / "input/roles/中国男1/中国男1_正面.png",
        IMAGES / "characters/中国男1_脸部近景.png",
    )
    make_face_crop(
        ROOT / "input/roles/中国女2/中国女2_正面.png",
        IMAGES / "characters/中国女2_脸部近景.png",
    )

    # The supplied scene frame already establishes the complete lineup and scale.
    Image.open(SCENE).convert("RGB").save(IMAGES / "character_lineup.png", format="PNG")
    Image.open(SCENE).convert("RGB").save(
        IMAGES / "scenes/装甲警车_车内全景与轴线.png", format="PNG"
    )
    Image.open(ROOT / "input/scenes/装甲警车/装甲警车_外饰三视图.png").convert("RGB").save(
        IMAGES / "scenes/装甲警车_外饰三视图.png", format="PNG"
    )

    plan_path = OTHERS / "shot_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    jobs = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(run_image_job, shot, i): shot["id"]
            for i, shot in enumerate(plan["shots"])
        }
        for future in as_completed(futures):
            record = future.result()
            jobs.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)

    failed = [x for x in jobs if x.get("error")]
    if failed:
        (OTHERS / "image_generation_failures.json").write_text(
            json.dumps(failed, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        raise RuntimeError(f"{len(failed)} image jobs failed")

    # Validate dimensions and write a complete purposes manifest.
    assets = []
    role_sources = {
        "中国男1": ROOT / "input/roles/中国男1",
        "中国女2": ROOT / "input/roles/中国女2",
        "警察探长": ROOT / "input/roles/警察探长",
    }
    for role, folder in role_sources.items():
        for path in sorted(folder.glob("*")):
            if path.suffix.lower() not in {".png", ".wav"}:
                continue
            assets.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "category": "character" if path.suffix.lower() == ".png" else "voice",
                    "identity": role,
                    "role": "user_reference",
                    "usage": "锁定角色身份、角度、服装、比例或 Speech 音色",
                    "sha256": sha256(path),
                }
            )
    for path in sorted(IMAGES.rglob("*.png")):
        with Image.open(path) as img:
            width, height = img.size
        assets.append(
            {
                "path": str(path.relative_to(ROOT)),
                "category": "generated_or_organized_static_asset",
                "role": "shot_reference_non_start_frame"
                if "/shots/" in str(path)
                else "visual_reference_pack",
                "usage": "逐镜构图/动作初态参考，非首帧"
                if "/shots/" in str(path)
                else "角色、场景或比例审查",
                "width": width,
                "height": height,
                "sha256": sha256(path),
            }
        )
    manifest = {
        "project": "车上聊天",
        "image_model": "gpt-image-2",
        "quality": "medium",
        "frame_strategy": "all dialogue shots use Ref2VA dialogue with reference_only images",
        "assets": assets,
        "generation_jobs": sorted(jobs, key=lambda x: x["shot_id"]),
        "status": "generated_pending_visual_qc",
    }
    (OTHERS / "generated_asset_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"completed={len(jobs)} failed=0", flush=True)


if __name__ == "__main__":
    main()
