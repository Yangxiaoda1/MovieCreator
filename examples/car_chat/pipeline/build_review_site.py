#!/usr/bin/env python3
"""Create/update the unified review site's project data and configuration."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output"
VIS = OUT / "vis"
TEMPLATE = ROOT / "aifilm_booklet" / "tools" / "vis"
# CloudBase 配置从环境变量读取（见 setup/aimovie_api.env.example），仓库中不保存真实值。
ENV_ID = os.environ.get("CLOUDBASE_ENV_ID", "your-cloudbase-env-id")
BUCKET = os.environ.get("CLOUDBASE_BUCKET", "your-bucket-name")
DOC_ID = os.environ.get("CLOUDBASE_DOC_ID", "car-chat-demo")
API_URL = os.environ.get("CLOUDBASE_API_URL", "")
DEPLOY_PATH = os.environ.get("CLOUDBASE_DEPLOY_PATH", "/car-chat-demo")


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def copy_template() -> None:
    VIS.mkdir(parents=True, exist_ok=True)
    for name in [
        "app.py",
        "run_vis.sh",
        "sync_public.py",
        "validate_vis.py",
        "README.md",
    ]:
        shutil.copy2(TEMPLATE / name, VIS / name)
    shutil.copytree(TEMPLATE / "public", VIS / "public", dirs_exist_ok=True)
    shutil.copytree(TEMPLATE / "functions", VIS / "functions", dirs_exist_ok=True)
    sync_path = VIS / "sync_public.py"
    sync_source = sync_path.read_text(encoding="utf-8")
    marker = '    ("output/images_prepare/", "assets/images_prepare/"),'
    if '("output/others/", "assets/others/"),' not in sync_source:
        sync_source = sync_source.replace(
            marker, marker + '\n    ("output/others/", "assets/others/"),'
        )
        sync_path.write_text(sync_source, encoding="utf-8")


def main() -> None:
    copy_template()
    plan = read_json(OUT / "others" / "shot_plan.json", {})
    manifest = read_json(OUT / "others" / "h3_candidate_manifest.json", {"jobs": {}})
    selected_manifest = read_json(OUT / "others" / "selected_manifest.json", {"shots": {}})
    final_4k = OUT / "final/movie_final_4k.mp4"
    final_4k_no_subtitles = OUT / "final/movie_final_4k_no_subtitles.mp4"
    final_video = (
        "output/final/movie_final_4k.mp4"
        if final_4k.exists()
        else (
            "output/final/movie_final.mp4"
            if (OUT / "final/movie_final.mp4").exists()
            else ""
        )
    )
    final_video_no_subtitles = (
        "output/final/movie_final_4k_no_subtitles.mp4"
        if final_4k_no_subtitles.exists()
        else (
            "output/final/movie_final_no_subtitles.mp4"
            if (OUT / "final/movie_final_no_subtitles.mp4").exists()
            else ""
        )
    )

    shots = plan.get("shots", [])
    for shot in shots:
        sid = shot["id"]
        candidates = []
        for candidate in (1, 2):
            key = f"{sid}_cand{candidate:02d}"
            rec = manifest.get("jobs", {}).get(key, {})
            path = rec.get("output", "")
            candidates.append(
                {
                    "id": f"cand{candidate:02d}",
                    "path": path,
                    "seed": rec.get(
                        "seed", 202609250000 + int(sid.split("_")[1]) * 10 + candidate
                    ),
                    "qc_status": rec.get("qc_status", rec.get("status", "pending")),
                    "note": rec.get("qc_note", f"MiniMax H3 Turbo 8-step 候选 {candidate}"),
                }
            )
        shot["candidate_videos"] = candidates
        selected = selected_manifest.get("shots", {}).get(sid, {})
        candidate_qc = {
            f"cand{x['candidate']:02d}": x
            for x in selected.get("candidate_qc", [])
        }
        for item in candidates:
            qc = candidate_qc.get(item["id"], {})
            if qc:
                item["qc_status"] = qc.get("status", item["qc_status"])
                item["note"] = (
                    f"ASR相似度 {qc.get('text_similarity', 0):.2%}；"
                    f"动态量 {qc.get('visual_metrics', {}).get('motion_score', 0)}；"
                    + ("主候选" if selected.get("selected_candidate") == item["id"] else "Pass")
                )
        shot["selected_video"] = selected.get("output", "")
        shot["upscaled_video"] = ""
        shot["reference_asset"] = shot["reference_assets"][0]["path"]

    # The public sync utility treats shot_plan.json as the canonical project
    # record. Persist review/runtime fields there so they are not discarded.
    plan["shots"] = shots
    plan.update(
        {
            "project_title": "车上聊天",
            "episode": "1–3",
            "aspect_ratio": "16:9",
            "target_duration_sec": sum(s["duration_sec"] for s in shots),
            "status": "final_review" if final_video else "production_in_progress",
            "description": "三人先遣小队在行驶中的装甲警车内谈论L5任务、机器人叛乱与智械解耦原则",
            "final_video": final_video,
            "final_video_no_subtitles": final_video_no_subtitles,
            "delivery_resolution": "3840x2160" if final_4k.exists() else "1920x1080",
        }
    )
    (OUT / "others" / "shot_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    storyboard = {
        "project_title": "车上聊天",
        "episode": "1–3",
        "aspect_ratio": "16:9",
        "target_duration_sec": sum(s["duration_sec"] for s in shots),
        "status": "final_review" if final_video else "production_in_progress",
        "description": "三人先遣小队在行驶中的装甲警车内谈论L5任务、机器人叛乱与智械解耦原则",
        "final_video": final_video,
        "final_video_no_subtitles": final_video_no_subtitles,
        "delivery_resolution": "3840x2160" if final_4k.exists() else "1920x1080",
        "overview_assets": [
            {
                "name": "输入资产总览",
                "description": "输入角色、场景与比例参考总览",
                "asset": "output/others/input_asset_contact_sheet.jpg",
            },
            {
                "name": "逐镜参考图总览",
                "description": "20个对白镜头的静态参考图",
                "asset": "output/others/shot_reference_contact_sheet.jpg",
            },
        ],
        "characters": [
            {
                "name": "中国男1｜三视图",
                "description": "青年男实习探员；前排驾驶；黑色短袖与黑色工装裤",
                "asset": "input/roles/中国男1/中国男1_三视图.png",
            },
            {
                "name": "中国男1｜脸部近景",
                "description": "由用户正面参考裁切的脸部审查图；音色参考已具备",
                "asset": "output/images_prepare/characters/中国男1_脸部近景.png",
            },
            {
                "name": "中国女2｜三视图",
                "description": "青年女探员；后排左侧；黑色皮夹克与白色背心",
                "asset": "input/roles/中国女2/中国女2_三视图.png",
            },
            {
                "name": "中国女2｜脸部近景",
                "description": "由用户正面参考裁切的脸部审查图；音色参考已具备",
                "asset": "output/images_prepare/characters/中国女2_脸部近景.png",
            },
            {
                "name": "警察探长｜三视图",
                "description": "中年现场指挥官；后排中右；黑色警务训练服",
                "asset": "input/roles/警察探长/警察探长_三视图.png",
            },
            {
                "name": "警察探长｜脸部近景",
                "description": "锁定成熟脸、短寸灰黑发和年龄感；音色参考已具备",
                "asset": "input/roles/警察探长/警察探长_脸部近景.png",
            },
            {
                "name": "三人比例与固定座位",
                "description": "中国男1前排驾驶；中国女2后排左侧；警察探长后排中右",
                "asset": "output/images_prepare/character_lineup.png",
            },
        ],
        "scenes": [
            {
                "name": "装甲警车车内",
                "description": "固定三人座位、黑色金属内壁、窄顶灯、防弹侧窗、行驶中的城市流光",
                "asset": "input/scenes/装甲警车/装甲警车_车内内饰_三人座位.png",
            },
            {
                "name": "车内轴线与稳定比例",
                "description": "固定前后排关系、摄影轴线、方向盘、防弹窗、顶灯和座椅比例",
                "asset": "output/images_prepare/scenes/装甲警车_车内全景与轴线.png",
            },
            {
                "name": "装甲警车外饰",
                "description": "深橄榄黑装甲SUV；仅作车辆身份与比例总览",
                "asset": "input/scenes/装甲警车/装甲警车_外饰三视图.png",
            },
        ],
        "props": [
            {
                "name": "方向盘、安全带与座椅",
                "description": "均为车内固定结构；保持真实接触、位置和尺寸，不得变形或忽隐忽现",
                "asset": "input/scenes/装甲警车/装甲警车_车内内饰_三人座位.png",
            }
        ],
        "shots": shots,
    }
    (VIS / "public" / "storyboard.json").write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    version = datetime.now().strftime("%Y%m%d-%H%M%S")
    (VIS / "public" / "cloudbase-config.js").write_text(
        "// 车上聊天统一公网审查配置\n"
        "window.STORYBOARD_CONFIG = {\n"
        f'  docId: "{DOC_ID}",\n'
        f'  apiUrl: "{API_URL}",\n'
        f'  assetVersion: "{version}"\n'
        "};\n",
        encoding="utf-8",
    )
    index = (VIS / "public" / "index.html").read_text(encoding="utf-8")
    import re

    index = re.sub(r"(style\.css)\?v=[^\"']+", rf"\1?v={version}", index)
    index = re.sub(r"(cloudbase-config\.js)\?v=[^\"']+", rf"\1?v={version}", index)
    index = re.sub(r"(app\.js)\?v=[^\"']+", rf"\1?v={version}", index)
    (VIS / "public" / "index.html").write_text(index, encoding="utf-8")

    cloudbaserc = {
        "$schema": "https://static.cloudbase.net/cli/cloudbaserc.schema.json",
        "envId": ENV_ID,
        "region": "ap-shanghai",
        "functionRoot": "functions",
        "functions": [
            {
                "name": "storyboardReviewApi",
                "type": "HTTP",
                "runtime": "Nodejs20.19",
                "timeout": 15,
                "memorySize": 128,
                "dir": "storyboardReviewApi",
                "installDependency": True,
                "description": "Public HTTP API for shared storyboard review notes",
                "public": True,
                "envVariables": {
                    "STORYBOARD_CLOUDBASE_ENV_ID": ENV_ID,
                    "STORYBOARD_CLOUDBASE_BUCKET": BUCKET,
                    "STORYBOARD_DEFAULT_DOC_ID": DOC_ID,
                },
            }
        ],
        "hosting": [
            {
                "name": "storyboard",
                "root": ".",
                "framework": "static",
                "installCommand": "",
                "buildCommand": "",
                "outputDir": "public",
                "deployPath": DEPLOY_PATH,
            }
        ],
    }
    (VIS / "cloudbaserc.json").write_text(
        json.dumps(cloudbaserc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (VIS / "review_notes.json").write_text(
        json.dumps({"notes": {}, "updatedAt": 0, "updatedBy": ""}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"version": version, "shots": len(shots)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
