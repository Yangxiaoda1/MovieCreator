#!/usr/bin/env python3
"""开跑前自检：系统命令 / Python 包 / ComfyUI 与节点 / 权重 / 凭据 / 服务端口。

    python setup/check_env.py            # 全部检查（需先 bash setup/start_comfyui.sh）
    python setup/check_env.py --offline  # 不检查 ComfyUI 服务
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
from download_models import SPEC, status  # noqa: E402

COMMANDS = ["ffmpeg", "ffprobe", "tmux", "git", "whisper", "node", "tcb"]
MODULES = ["torch", "torchaudio", "cv2", "numpy", "PIL", "requests", "whisper", "scenedetect", "huggingface_hub"]
SECRETS = ["AIMOVIE_IMAGE_APP_ID", "AIMOVIE_IMAGE_APP_KEY", "AIMOVIE_IMAGE_ENDPOINT", "ELEVENLABS_APP_ID", "ELEVENLABS_APP_KEY"]
H3_PORTS = [8188, 8189, 8190, 8191]
ACE_PORT = 8192
H3_NODES = ["MiniMaxH3TurboLoRA", "MiniMaxH3TurboSampler", "MiniMaxH3ReferenceToVideo", "MiniMaxH3AddGuide"]
SEEDVR2_NODES = ["SeedVR2Preprocess", "SeedVR2Conditioning", "SeedVR2PostProcessing", "SeedVR2TemporalChunk"]
ACE_NODES = ["TextEncodeAceStepAudio1.5", "EmptyAceStep1.5LatentAudio", "VAEDecodeAudio"]

failed = 0


def report(ok: bool, label: str, hint: str = "") -> None:
    global failed
    failed += not ok
    print(f"  [{'OK' if ok else 'XX'}] {label}" + ("" if ok or not hint else f"  -> {hint}"))


def read_secrets() -> dict:
    path = Path(os.environ.get("AIMOVIE_SECRET_FILE", WORKSPACE / ".secrets" / "aimovie_api.env"))
    if not path.is_file():
        return {}
    out = subprocess.run(
        ["bash", "-c", f'set -a; source "{path}"; env -0'], capture_output=True, check=False
    ).stdout.split(b"\0")
    return dict(item.decode().split("=", 1) for item in out if b"=" in item)


def object_info(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/object_info", timeout=20) as r:
            return json.loads(r.read())
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    print("系统命令")
    for cmd in COMMANDS:
        report(shutil.which(cmd) is not None, cmd, "tcb: npm i -g @cloudbase/cli；node>=18")
    enc = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True).stdout if shutil.which("ffmpeg") else ""
    report("libx264" in enc, "ffmpeg 带 libx264")

    print("Python 包")
    for mod in MODULES:
        report(importlib.util.find_spec(mod) is not None, mod, "pip install -r setup/requirements.txt")
    try:
        import torch

        n = torch.cuda.device_count()
        report(n >= 1, f"CUDA GPU x{n}", "需要 NVIDIA GPU；推荐 4 x 80GB+")
    except Exception as e:  # pragma: no cover
        report(False, f"torch.cuda ({e})")

    print("ComfyUI")
    report((WORKSPACE / "ComfyUI" / "main.py").is_file(), "ComfyUI/", "bash setup/install.sh")
    report((WORKSPACE / "ComfyUI/custom_nodes/ComfyUI-MiniMax-H3-Turbo/__init__.py").is_file(),
           "custom_nodes/ComfyUI-MiniMax-H3-Turbo", "bash setup/install.sh")
    foley = (WORKSPACE / "third_party/HunyuanVideo-Foley/infer.py").is_file()
    print(f"  [{'OK' if foley else '--'}] third_party/HunyuanVideo-Foley（可选，S15）")

    print("权重")
    for name, group in SPEC["groups"].items():
        optional = name == "foley"
        for item in group["files"]:
            state, path = status(item)
            if optional and state != "ok":
                print(f"  [--] {path.relative_to(WORKSPACE)} ({state}，可选)")
                continue
            report(state == "ok", f"{path.relative_to(WORKSPACE)}", f"{state}; python setup/download_models.py --only {name}")

    print("凭据 .secrets/aimovie_api.env")
    env = read_secrets()
    report(bool(env), ".secrets/aimovie_api.env 存在", "cp setup/aimovie_api.env.example .secrets/aimovie_api.env")
    for key in SECRETS:
        report(bool(env.get(key)), key, "在 .secrets/aimovie_api.env 中填写")

    if not args.offline:
        print("ComfyUI 服务")
        for port in H3_PORTS:
            info = object_info(port)
            if info is None:
                report(False, f":{port}", "bash setup/start_comfyui.sh")
                continue
            missing = [n for n in H3_NODES + SEEDVR2_NODES if n not in info]
            report(not missing, f":{port} H3 + SeedVR2 节点", f"缺少 {missing}")
        info = object_info(ACE_PORT)
        if info is None:
            report(False, f":{ACE_PORT} ACE-Step", "bash setup/start_comfyui.sh（检查 ACE_GPU）")
        else:
            missing = [n for n in ACE_NODES if n not in info]
            report(not missing, f":{ACE_PORT} ACE-Step 节点", f"缺少 {missing}")

    print("\n全部通过" if failed == 0 else f"\n{failed} 项未通过")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
