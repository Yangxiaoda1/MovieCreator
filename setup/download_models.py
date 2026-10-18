#!/usr/bin/env python3
"""Download all open-source weights listed in setup/models.json into <WORKSPACE>.

Usage:
    python setup/download_models.py                 # 全部
    python setup/download_models.py --only h3 seedvr2
    python setup/download_models.py --check         # 只校验，不下载

HF 访问慢时可先 export HF_ENDPOINT=https://hf-mirror.com ；私有/限流时 export HF_TOKEN=...
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
SPEC = json.loads((Path(__file__).with_name("models.json")).read_text(encoding="utf-8"))


def human(n: int) -> str:
    return f"{n / 1024**3:.2f} GB"


def status(item: dict) -> tuple[str, Path]:
    path = WORKSPACE / item["target"] / item["file"]
    if not path.exists():
        return "missing", path
    real = path.stat().st_size
    if real != item["size"]:
        return f"size_mismatch({real} != {item['size']})", path
    return "ok", path


def locate(api, repo: str, name: str, cache: dict) -> str:
    if repo not in cache:
        cache[repo] = api.list_repo_files(repo)
    hits = [f for f in cache[repo] if f.split("/")[-1] == name]
    if not hits:
        raise FileNotFoundError(f"{name} not found in {repo}")
    return hits[0]


def download(item: dict, api, cache: dict) -> None:
    from huggingface_hub import hf_hub_download

    remote = locate(api, item["repo"], item["file"], cache)
    staging = WORKSPACE / ".hf_staging" / item["repo"].replace("/", "__")
    print(f"  downloading {item['repo']}/{remote} ({human(item['size'])})", flush=True)
    got = Path(hf_hub_download(item["repo"], remote, local_dir=staging))
    dest = WORKSPACE / item["target"] / item["file"]
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    shutil.move(str(got), dest)


def main() -> int:
    groups = SPEC["groups"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", choices=sorted(groups), help="只处理指定分组")
    ap.add_argument("--check", action="store_true", help="只校验，不下载")
    ap.add_argument("--skip-whisper", action="store_true")
    args = ap.parse_args()
    selected = args.only or list(groups)

    api = cache = None
    if not args.check:
        from huggingface_hub import HfApi

        api, cache = HfApi(), {}

    bad = 0
    for name in selected:
        group = groups[name]
        print(f"[{name}] {group['desc']}")
        for item in group["files"]:
            state, path = status(item)
            if state != "ok" and not args.check:
                download(item, api, cache)
                state, path = status(item)
            print(f"  {state:<10} {path.relative_to(WORKSPACE)}")
            bad += state != "ok"
        for repo in group.get("hf_snapshots", []):
            if args.check:
                print(f"  (runtime)  HF cache: {repo}")
                continue
            from huggingface_hub import snapshot_download

            print(f"  caching    {repo}", flush=True)
            snapshot_download(repo)

    if not args.skip_whisper and not args.only:
        if args.check:
            cache_file = Path(os.path.expanduser("~/.cache/whisper/small.pt"))
            state = "ok" if cache_file.exists() else "missing"
            print(f"[whisper] {state:<10} {cache_file}")
            bad += state != "ok"
        else:
            import whisper

            print("[whisper] caching openai-whisper small", flush=True)
            whisper.load_model("small", device="cpu")

    shutil.rmtree(WORKSPACE / ".hf_staging", ignore_errors=True)
    print("ALL OK" if bad == 0 else f"{bad} file(s) missing or incomplete")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
