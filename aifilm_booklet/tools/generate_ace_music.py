#!/usr/bin/env python3
"""Generate the instrumental score with ACE-Step 1.5 through ComfyUI."""

import json
import time
import urllib.request
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "interaction" / "output"
WORKFLOW = OUTPUT / "others" / "audio_tools" / "ace_music_workflow.json"
MANIFEST = OUTPUT / "audio" / "music" / "manifest.json"
SERVER = "http://127.0.0.1:8192"


def request_json(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"} if data else {}
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def graph():
    return {
        "1": {
            "class_type": "UNETLoader",
            "inputs": {
                "unet_name": "acestep_v1.5_turbo.safetensors",
                "weight_dtype": "default",
            },
        },
        "2": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1": "qwen_0.6b_ace15.safetensors",
                "clip_name2": "qwen_4b_ace15.safetensors",
                "type": "ace",
                "device": "default",
            },
        },
        "3": {
            "class_type": "VAELoader",
            "inputs": {"vae_name": "ace_1.5_vae.safetensors"},
        },
        "4": {
            "class_type": "TextEncodeAceStepAudio1.5",
            "inputs": {
                "clip": ["2", 0],
                "tags": (
                    "strictly instrumental background score, absolutely no human voice, no vocals, "
                    "no singing, no humming, no chanting, no spoken words, "
                    "cinematic Chinese rural comedy score, "
                    "warm chamber strings, bamboo flute, light pizzicato, subtle woodblock and low drum, "
                    "clear narrative arc: calm dawn opening, playful study contrast, restrained suspense "
                    "during the exam, comic tension during failed tricks, sudden mischievous energy for "
                    "the confrontation, bright clever reveal at the willow tree, warm reconciliatory ending; "
                    "sparse arrangement under dialogue, elegant natural dynamics, no trailer braams, "
                    "no electronic dance beat, no choir"
                ),
                "lyrics": "",
                "seed": 2026090801,
                "bpm": 92,
                "duration": 80.0,
                "timesignature": "4",
                "language": "zh",
                "keyscale": "G major",
                "generate_audio_codes": False,
                "cfg_scale": 2.0,
                "temperature": 0.85,
                "top_p": 0.9,
                "top_k": 0,
                "min_p": 0.0,
            },
        },
        "5": {
            "class_type": "ConditioningZeroOut",
            "inputs": {"conditioning": ["4", 0]},
        },
        "6": {
            "class_type": "EmptyAceStep1.5LatentAudio",
            "inputs": {"seconds": 80.0, "batch_size": 1},
        },
        "7": {
            "class_type": "ModelSamplingAuraFlow",
            "inputs": {"model": ["1", 0], "shift": 3.0},
        },
        "8": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["7", 0],
                "seed": 2026090801,
                "steps": 8,
                "cfg": 1.0,
                "sampler_name": "euler",
                "scheduler": "simple",
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
                "denoise": 1.0,
            },
        },
        "9": {
            "class_type": "VAEDecodeAudio",
            "inputs": {"samples": ["8", 0], "vae": ["3", 0]},
        },
        "10": {
            "class_type": "SaveAudio",
            "inputs": {
                "audio": ["9", 0],
                "filename_prefix": "audio/music/ace_step_score",
            },
        },
    }


def main():
    workflow = graph()
    WORKFLOW.parent.mkdir(parents=True, exist_ok=True)
    WORKFLOW.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    response = request_json(
        SERVER + "/prompt",
        {"prompt": workflow, "client_id": f"ace-score-{uuid.uuid4()}"},
    )
    prompt_id = response["prompt_id"]
    print(f"submitted {prompt_id}", flush=True)
    started = time.monotonic()
    while True:
        history = request_json(SERVER + f"/history/{prompt_id}")
        if prompt_id in history:
            item = history[prompt_id]
            status = item.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(json.dumps(status, ensure_ascii=False))
            if status.get("completed") is True:
                candidates = []
                for node in item.get("outputs", {}).values():
                    if not isinstance(node, dict):
                        continue
                    for key in ("audio", "images", "videos"):
                        for result in node.get(key, []):
                            if result.get("filename"):
                                candidates.append(
                                    OUTPUT / result.get("subfolder", "") / result["filename"]
                                )
                if not candidates:
                    candidates = sorted((OUTPUT / "audio" / "music").glob("ace_step_score*"))
                if not candidates:
                    raise RuntimeError("ACE-Step completed without an output file")
                manifest = {
                    "engine": "ACE-Step 1.5",
                    "prompt_id": prompt_id,
                    "output": str(candidates[-1]),
                    "duration_sec": 80.0,
                    "elapsed_sec": round(time.monotonic() - started, 2),
                    "workflow": str(WORKFLOW),
                }
                MANIFEST.parent.mkdir(parents=True, exist_ok=True)
                MANIFEST.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(json.dumps(manifest, ensure_ascii=False), flush=True)
                return
        time.sleep(10)


if __name__ == "__main__":
    main()
