#!/usr/bin/env python3
"""Generate per-shot ambience and effects with HunyuanVideo-Foley."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

import torch
import torchaudio

ROOT = Path("/apdcephfs_gy2/share_302507476/xiaodayang/aimovie")
OUTPUT = ROOT / "interaction" / "output"
REPO = OUTPUT / "others" / "audio_tools" / "src" / "HunyuanVideo-Foley"
sys.path.insert(0, str(REPO))

from hunyuanvideo_foley.utils.model_utils import load_model
from infer import infer, set_manual_seed


SOURCE = OUTPUT / "video_raw" / "selected"
DEST = OUTPUT / "audio" / "sound" / "raw"
MODEL_DIR = OUTPUT / "others" / "audio_tools" / "models" / "HunyuanVideo-Foley"
CONFIG = REPO / "configs" / "hunyuanvideo-foley-xl.yaml"
PLAN = OUTPUT / "others" / "shot_plan.json"
MANIFEST = OUTPUT / "audio" / "sound" / "manifest.json"


PROMPTS = {
    "shot_001": "Early morning birds and soft willow leaves outside, then quiet classroom room tone, chalk gently placed on a wooden lectern and subtle clothing rustle. No speech, no voices, no music.",
    "shot_002": "Quiet classroom page turns and pencils writing, one soft sleepy yawn, then outdoor cicadas and gentle footsteps under a willow tree. No speech, no voices, no music.",
    "shot_003": "Hot noon classroom ambience, prominent wall clock ticking, subtle chair and clothing movement, tense stillness. No speech, no voices, no music.",
    "shot_004": "Quiet classroom, urgent pointing gestures, paper letter handling, soft kneeling cloth movement, restrained sobbing breaths, clock ticking. No intelligible speech, no music.",
    "shot_005": "Quiet classroom room tone, small hand gestures, one brief restrained chuckle from the teacher, faint clock tick. No intelligible speech, no music.",
    "shot_006": "Muggy classroom with distant cicadas, close wall clock ticks, nervous shifting, soft snoring, then a large yawn and feet standing up. No speech, no music.",
    "shot_007": "Fast footsteps across classroom, hands gripping and bunching a suit lapel, tense fabric creaks, desks lightly bumping, shocked gasps. No intelligible speech, no punches, no music.",
    "shot_008": "Angry pointing gesture, hurried footsteps, two people carrying another across the classroom, door movement, shoes crossing a threshold, indoor echo changing to outdoor cicadas. No intelligible speech, no music.",
    "shot_009": "Outdoor cicadas and willow leaves, delighted laughter, footsteps to the willow tree, hand grasps a thin leafy twig, a crisp small branch snap, twig rustling. No intelligible speech, no music.",
    "shot_010": "Quiet classroom, respectful kneeling cloth movement, leafy willow twig rustle, teacher helps someone stand, relieved breaths followed by warm group laughter. No intelligible speech, no music.",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--shots", nargs="*")
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    set_manual_seed(20260908)
    DEST.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda:0")
    model_dict, cfg = load_model(
        str(MODEL_DIR), str(CONFIG), device, enable_offload=False, model_size="xl"
    )
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    records = {}
    for index, shot in enumerate(plan["shots"]):
        shot_id = shot["id"]
        if args.shots and shot_id not in set(args.shots):
            continue
        video = SOURCE / f"{shot_id}.mp4"
        output = DEST / f"{shot_id}.wav"
        if output.exists() and not args.force:
            records[shot_id] = {
                "video": str(video),
                "prompt": PROMPTS[shot_id],
                "output": str(output),
                "sample_rate": 48000,
                "resumed": True,
            }
            print(f"[resume] {shot_id} -> {output}", flush=True)
            continue
        set_manual_seed(20260908 + index)
        audio, sample_rate = infer(
            str(video),
            PROMPTS[shot_id],
            model_dict,
            cfg,
            guidance_scale=4.5,
            num_inference_steps=args.steps,
            neg_prompt="speech, dialogue, words, narration, singing, song, background music, noisy, harsh",
        )
        torchaudio.save(output, audio, sample_rate)
        subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-f", "null", "-"], check=True)
        records[shot_id] = {
            "video": str(video),
            "prompt": PROMPTS[shot_id],
            "output": str(output),
            "sample_rate": sample_rate,
        }
        print(f"[{index + 1}/10] {shot_id} -> {output}", flush=True)
        MANIFEST.write_text(
            json.dumps(
                {"engine": "HunyuanVideo-Foley XL", "shots": records},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
