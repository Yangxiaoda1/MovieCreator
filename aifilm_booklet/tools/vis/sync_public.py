#!/usr/bin/env python3
from __future__ import annotations
import json
import shutil
from pathlib import Path

VIS = Path(__file__).resolve().parent
# This file can be run either from the reusable template
#   <PROJECT_ROOT>/aifilm_booklet/tools/vis/
# or from the copied project instance
#   <PROJECT_ROOT>/output/vis/
if VIS.parent.name == "output":
    PROJECT_ROOT = VIS.parent.parent
    OUTPUT = VIS.parent
else:
    PROJECT_ROOT = VIS.parents[2]
    OUTPUT = PROJECT_ROOT / "output"
PUBLIC = VIS / "public"
ASSETS = PUBLIC / "assets"
PROJECT_PREFIX_MAPPINGS = (
    ("output/images_prepare/", "assets/images_prepare/"),
    ("output/video_raw/", "assets/video_raw/"),
    ("output/videos/", "assets/videos/"),  # legacy projects
    ("output/resolution/", "assets/resolution/"),
    ("output/final/", "assets/final/"),
    ("output/audio/", "assets/audio/"),
    ("output/frames_review/", "assets/frames_review/"),
    ("input/roles/", "assets/characters/"),
    ("input/scenes/", "assets/scenes/"),
    ("input/other/", "assets/input/other/"),
    ("input/others/", "assets/input/others/"),
)


def copy_file(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, dirs_exist_ok=True)


def public_asset_path(value: str) -> str:
    """Map a project-relative path to the matching public/assets path."""
    raw = str(value or "").strip().replace("\\", "/")
    if not raw or raw.startswith(("http://", "https://", "data:", "blob:", "assets/")):
        return raw
    project_prefix = PROJECT_ROOT.as_posix().rstrip("/") + "/"
    if raw.startswith(project_prefix):
        raw = raw[len(project_prefix):]
    for source_prefix, public_prefix in PROJECT_PREFIX_MAPPINGS:
        if raw.startswith(source_prefix):
            return public_prefix + raw[len(source_prefix):]
    return raw


def rewrite_asset_paths(value):
    if isinstance(value, dict):
        return {key: rewrite_asset_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [rewrite_asset_paths(item) for item in value]
    if isinstance(value, str):
        return public_asset_path(value)
    return value


def collect_project_asset_pairs(original, rewritten) -> list[tuple[Path, Path]]:
    """Collect exact source/destination pairs for every rewritten local asset."""
    pairs: list[tuple[Path, Path]] = []
    if isinstance(original, dict) and isinstance(rewritten, dict):
        for key, value in original.items():
            if key in rewritten:
                pairs.extend(collect_project_asset_pairs(value, rewritten[key]))
    elif isinstance(original, list) and isinstance(rewritten, list):
        for before, after in zip(original, rewritten):
            pairs.extend(collect_project_asset_pairs(before, after))
    elif isinstance(original, str) and isinstance(rewritten, str):
        if not rewritten.startswith("assets/"):
            return pairs
        raw = original.strip().replace("\\", "/")
        if raw.startswith(("http://", "https://", "data:", "blob:", "assets/")):
            return pairs
        source = Path(raw)
        if not source.is_absolute():
            source = PROJECT_ROOT / source
        target = PUBLIC / rewritten.split("?", 1)[0]
        pairs.append((source, target))
    return pairs


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    referenced_pairs: list[tuple[Path, Path]] = []
    plan = OUTPUT / "others" / "shot_plan.json"
    if plan.exists():
        plan_data = json.loads(plan.read_text(encoding="utf-8"))
        storyboard_path = PUBLIC / "storyboard.json"
        storyboard = {}
        if storyboard_path.exists():
            current = json.loads(storyboard_path.read_text(encoding="utf-8"))
            if isinstance(current, dict):
                storyboard.update(current)
        if isinstance(plan_data, dict):
            # Preserve template-only defaults, but let every real project field
            # (including final_video and future schema additions) override them.
            storyboard.update(plan_data)
        original_storyboard = storyboard
        storyboard = rewrite_asset_paths(original_storyboard)
        referenced_pairs = collect_project_asset_pairs(original_storyboard, storyboard)
        storyboard_path.write_text(
            json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        storyboard_path = PUBLIC / "storyboard.json"
        if storyboard_path.exists():
            original_storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))
            storyboard = rewrite_asset_paths(original_storyboard)
            referenced_pairs = collect_project_asset_pairs(original_storyboard, storyboard)
            storyboard_path.write_text(
                json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    # Copy each local file referenced by storyboard.json. This keeps arbitrary
    # subdirectories such as output/video_raw/reference_clips/ working without
    # copying every generated candidate into the public deployment.
    copied = 0
    missing_sources: list[str] = []
    seen: set[tuple[str, str]] = set()
    for source, target in referenced_pairs:
        pair = (str(source), str(target))
        if pair in seen:
            continue
        seen.add(pair)
        if source.is_file():
            copy_file(source, target)
            copied += 1
        elif source.is_dir():
            copy_tree(source, target)
            copied += 1
        elif not target.exists():
            missing_sources.append(str(source))

    # These small source-asset trees are useful for asset overviews even when
    # the shot plan does not enumerate every file.
    copy_tree(PROJECT_ROOT / "input" / "roles", ASSETS / "characters")
    copy_tree(PROJECT_ROOT / "input" / "scenes", ASSETS / "scenes")
    copy_tree(PROJECT_ROOT / "input" / "other", ASSETS / "input" / "other")
    copy_tree(PROJECT_ROOT / "input" / "others", ASSETS / "input" / "others")
    print(f"vis public synced: {copied} referenced local assets copied")
    if missing_sources:
        print("warning: referenced source files not found:")
        for source in missing_sources[:20]:
            print(f"  - {source}")


if __name__ == "__main__":
    main()
