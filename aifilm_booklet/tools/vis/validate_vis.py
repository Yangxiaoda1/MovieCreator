#!/usr/bin/env python3
"""Validate a copied storyboard review site before deployment."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def collect_asset_references(value) -> set[str]:
    refs: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            refs.update(collect_asset_references(item))
    elif isinstance(value, list):
        for item in value:
            refs.update(collect_asset_references(item))
    elif isinstance(value, str) and value.startswith("assets/"):
        refs.add(value.split("?", 1)[0])
    return refs


def collect_unpublished_local_paths(value) -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            paths.update(collect_unpublished_local_paths(item))
    elif isinstance(value, list):
        for item in value:
            paths.update(collect_unpublished_local_paths(item))
    elif isinstance(value, str):
        normalized = value.strip().replace("\\", "/")
        if normalized.startswith(("output/", "input/", "/")):
            paths.add(normalized)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vis-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    vis = args.vis_dir.resolve()
    public = vis / "public"
    errors: list[str] = []
    warnings: list[str] = []

    required = [
        public / "index.html",
        public / "style.css",
        public / "app.js",
        public / "cloudbase-config.js",
        public / "storyboard.json",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing required file: {path}")

    data = {}
    if (public / "storyboard.json").is_file():
        try:
            data = json.loads((public / "storyboard.json").read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                errors.append("storyboard.json root must be an object")
            elif not isinstance(data.get("shots"), list):
                errors.append("storyboard.json must contain a shots array")
        except Exception as error:
            errors.append(f"invalid storyboard.json: {error}")

    if (public / "app.js").is_file():
        source = (public / "app.js").read_text(encoding="utf-8")
        if "ASSET_VERSION" in source and "const ASSET_VERSION" not in source:
            errors.append("app.js uses ASSET_VERSION but does not define it")
        if shutil.which("node"):
            checked = subprocess.run(
                ["node", "--check", str(public / "app.js")],
                text=True,
                capture_output=True,
            )
            if checked.returncode:
                errors.append(f"app.js syntax error: {checked.stderr.strip()}")
        else:
            warnings.append("node is unavailable; skipped JavaScript syntax check")

    if (public / "index.html").is_file():
        html = (public / "index.html").read_text(encoding="utf-8")
        config_pos = html.find("cloudbase-config.js")
        app_pos = html.find("app.js")
        if config_pos < 0 or app_pos < 0:
            errors.append("index.html must load cloudbase-config.js and app.js")
        elif config_pos > app_pos:
            errors.append("cloudbase-config.js must load before app.js")

    symlinks = [str(path) for path in (public / "assets").rglob("*") if path.is_symlink()] if (public / "assets").exists() else []
    if symlinks:
        errors.append(f"public/assets contains symlinks: {symlinks[:10]}")

    refs = sorted(collect_asset_references(data))
    missing = [ref for ref in refs if not (public / ref).is_file()]
    if missing:
        errors.append(f"missing referenced assets ({len(missing)}): {missing[:20]}")
    unpublished = sorted(collect_unpublished_local_paths(data))
    if unpublished:
        errors.append(
            "storyboard.json still contains local paths instead of public assets "
            f"({len(unpublished)}): {unpublished[:20]}"
        )

    config = (public / "cloudbase-config.js").read_text(encoding="utf-8") if (public / "cloudbase-config.js").is_file() else ""
    if "your-cloudbase-env-id" in config or "storyboard-review-demo" in config:
        warnings.append("cloudbase-config.js still contains template placeholders")
    if "service.tcloudbase.com" in config:
        warnings.append("prefer the verified HTTP gateway form: <env>-<uin>.<region>.app.tcloudbase.com/<path>")
    if not re.search(r"\bassetVersion\s*:\s*[\"'][^\"']+[\"']", config):
        errors.append("cloudbase-config.js must define a non-empty assetVersion")
    if re.search(r"\bapiUrl\s*:\s*[\"']https?://", config) and not re.search(
        r"\.app\.tcloudbase\.com/", config
    ):
        warnings.append("apiUrl does not use the verified <region>.app.tcloudbase.com gateway form")

    cloudbaserc = vis / "cloudbaserc.json"
    if cloudbaserc.is_file():
        try:
            cloudbase_data = json.loads(cloudbaserc.read_text(encoding="utf-8"))
            env_id = str(cloudbase_data.get("envId", ""))
            if not env_id or env_id.startswith("your-"):
                warnings.append("cloudbaserc.json still contains a placeholder envId")
            functions = cloudbase_data.get("functions", [])
            for function in functions if isinstance(functions, list) else []:
                variables = function.get("envVariables", {}) if isinstance(function, dict) else {}
                if any(str(value).startswith("your-") for value in variables.values()):
                    warnings.append("cloudbaserc.json function environment variables contain placeholders")
                    break
        except Exception as error:
            errors.append(f"invalid cloudbaserc.json: {error}")

    result = {
        "ok": not errors,
        "vis_dir": str(vis),
        "shot_count": len(data.get("shots", [])) if isinstance(data, dict) else 0,
        "asset_reference_count": len(refs),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
