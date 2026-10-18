#!/usr/bin/env python3
"""Client for the internal GPT Image gateway used by the AI movie pipeline.

Required environment variables:
    AIMOVIE_IMAGE_APP_ID
    AIMOVIE_IMAGE_APP_KEY

Optional:
    AIMOVIE_IMAGE_ENDPOINT
    AIMOVIE_IMAGE_MODEL
    AIMOVIE_IMAGE_PROVIDER
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path

import requests


DEFAULT_ENDPOINT = "http://trpc-gpt-eval.production.polaris:8080/v1/images/generations"


def generate_image(
    prompt: str,
    output: Path,
    *,
    size: str = "1536x1024",
    quality: str = "medium",
    timeout: int = 600,
    force: bool = False,
) -> Path:
    app_id = os.environ.get("AIMOVIE_IMAGE_APP_ID")
    app_key = os.environ.get("AIMOVIE_IMAGE_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError("Set AIMOVIE_IMAGE_APP_ID and AIMOVIE_IMAGE_APP_KEY")
    if output.exists() and not force:
        return output

    model = os.environ.get("AIMOVIE_IMAGE_MODEL", "gpt-image-2")
    provider = os.environ.get("AIMOVIE_IMAGE_PROVIDER", "openai")
    endpoint = os.environ.get("AIMOVIE_IMAGE_ENDPOINT", DEFAULT_ENDPOINT)
    auth = f"Bearer {app_id}:{app_key}?provider={provider}&model={model}&timeout={timeout}"
    response = requests.post(
        endpoint,
        headers={
            "Authorization": auth,
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality,
        },
        timeout=timeout + 10,
    )
    if not response.ok:
        body = response.text[:2000]
        raise RuntimeError(f"Image gateway HTTP {response.status_code}: {body}")
    payload = response.json()
    item = payload["data"][0]
    output.parent.mkdir(parents=True, exist_ok=True)
    if item.get("b64_json"):
        output.write_bytes(base64.b64decode(item["b64_json"]))
    elif item.get("url"):
        image_response = requests.get(item["url"], timeout=timeout)
        image_response.raise_for_status()
        output.write_bytes(image_response.content)
    else:
        raise RuntimeError("Image gateway response has neither b64_json nor url")
    return output


def edit_image(
    images: list[Path],
    prompt: str,
    output: Path,
    *,
    size: str = "1536x1024",
    quality: str = "medium",
    timeout: int = 600,
    force: bool = False,
) -> Path:
    app_id = os.environ.get("AIMOVIE_IMAGE_APP_ID")
    app_key = os.environ.get("AIMOVIE_IMAGE_APP_KEY")
    if not app_id or not app_key:
        raise RuntimeError("Set AIMOVIE_IMAGE_APP_ID and AIMOVIE_IMAGE_APP_KEY")
    if output.exists() and not force:
        return output

    model = os.environ.get("AIMOVIE_IMAGE_MODEL", "gpt-image-2")
    provider = os.environ.get("AIMOVIE_IMAGE_PROVIDER", "openai")
    generation_endpoint = os.environ.get("AIMOVIE_IMAGE_ENDPOINT", DEFAULT_ENDPOINT)
    endpoint = os.environ.get(
        "AIMOVIE_IMAGE_EDIT_ENDPOINT",
        generation_endpoint.rsplit("/", 1)[0] + "/edits",
    )
    auth = f"Bearer {app_id}:{app_key}?provider={provider}&model={model}&timeout={timeout}"
    opened = []
    try:
        files = []
        for image in images:
            handle = image.open("rb")
            opened.append(handle)
            files.append(("image[]", (image.name, handle, "image/png")))
        response = requests.post(
            endpoint,
            headers={"Authorization": auth},
            data={
                "model": model,
                "prompt": prompt,
                "n": "1",
                "size": size,
                "quality": quality,
            },
            files=files,
            timeout=timeout + 10,
        )
    finally:
        for handle in opened:
            handle.close()
    if not response.ok:
        raise RuntimeError(f"Image edit gateway HTTP {response.status_code}: {response.text[:2000]}")
    item = response.json()["data"][0]
    output.parent.mkdir(parents=True, exist_ok=True)
    if item.get("b64_json"):
        output.write_bytes(base64.b64decode(item["b64_json"]))
    elif item.get("url"):
        image_response = requests.get(item["url"], timeout=timeout)
        image_response.raise_for_status()
        output.write_bytes(image_response.content)
    else:
        raise RuntimeError("Image edit gateway response has neither b64_json nor url")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--edit", action="store_true")
    parser.add_argument("--image", action="append", type=Path, default=[])
    parser.add_argument("--prompt")
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--size", default="1536x1024")
    parser.add_argument("--quality", choices=["low", "medium", "high", "auto"], default="medium")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if bool(args.prompt) == bool(args.prompt_file):
        raise ValueError("Provide exactly one of --prompt or --prompt-file")
    prompt = args.prompt or args.prompt_file.read_text(encoding="utf-8")
    if args.edit:
        if not args.image:
            raise ValueError("--edit requires at least one --image")
        result = edit_image(
            args.image,
            prompt,
            args.out,
            size=args.size,
            quality=args.quality,
            timeout=args.timeout,
            force=args.force,
        )
    else:
        result = generate_image(
            prompt,
            args.out,
            size=args.size,
            quality=args.quality,
            timeout=args.timeout,
            force=args.force,
        )
    print(result)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
