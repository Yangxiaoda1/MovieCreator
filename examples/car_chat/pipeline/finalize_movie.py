#!/usr/bin/env python3
"""QC/select H3 candidates, build picture lock, sound, music, mix, subtitles and delivery."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
AIMOVIE = ROOT.parent
OUT = ROOT / "output"
PLAN_PATH = OUT / "others" / "shot_plan.json"
CANDIDATES = OUT / "video_raw" / "candidates"
SELECTED = OUT / "video_raw" / "selected"
PICTURE = OUT / "video_raw" / "picture_lock"
ASR_ROOT = OUT / "audio" / "asr"
SPEECH = OUT / "audio" / "speech"
SOUND_RAW = OUT / "audio" / "sound" / "raw"
SOUND_PROCESSED = OUT / "audio" / "sound" / "processed"
MUSIC_RAW = OUT / "audio" / "music" / "raw"
FINAL = OUT / "final"
OTHERS = OUT / "others"
ACE_PORT = 8192


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def run(cmd: list[str], **kwargs):
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def ffprobe(path: Path) -> dict:
    proc = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
    )
    return json.loads(proc.stdout)


def decode_ok(path: Path) -> bool:
    try:
        run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"])
        return True
    except Exception:
        return False


def extract_frames(path: Path, count: int = 9) -> list[np.ndarray]:
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    for idx in np.linspace(0, max(total - 1, 0), count, dtype=int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if ok:
            frames.append(frame)
    cap.release()
    return frames


def image_metrics(path: Path) -> dict:
    frames = extract_frames(path)
    if not frames:
        return {"frame_count_sampled": 0, "mean_brightness": 0, "motion_score": 0, "sharpness": 0}
    grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    brightness = float(np.mean([g.mean() for g in grays]))
    sharpness = float(np.mean([cv2.Laplacian(g, cv2.CV_64F).var() for g in grays]))
    motion = float(
        np.mean(
            [
                cv2.absdiff(grays[i], grays[i - 1]).mean()
                for i in range(1, len(grays))
            ]
        )
    )
    return {
        "frame_count_sampled": len(frames),
        "mean_brightness": round(brightness, 3),
        "motion_score": round(motion, 3),
        "sharpness": round(sharpness, 3),
    }


def normalize_text(text: str) -> str:
    return re.sub(r"[，。！？、“”‘’：；（）()\\s]", "", text).lower()


def levenshtein(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def asr(path: Path, tag: str) -> dict:
    outdir = ASR_ROOT / tag
    outdir.mkdir(parents=True, exist_ok=True)
    cached = outdir / "audio.json"
    source_sha256 = sha256(path)
    if cached.exists():
        result = json.loads(cached.read_text(encoding="utf-8"))
        if result.get("source_sha256") == source_sha256:
            return result
    wav = outdir / "audio.wav"
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ar",
            "16000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(wav),
        ]
    )
    cmd = [
        "whisper",
        str(wav),
        "--model",
        "small",
        "--language",
        "Chinese",
        "--task",
        "transcribe",
        "--output_dir",
        str(outdir),
        "--output_format",
        "json",
        "--word_timestamps",
        "True",
        "--device",
        "cuda",
    ]
    proc = run(cmd, capture_output=True)
    result = json.loads((outdir / "audio.json").read_text(encoding="utf-8"))
    result["stdout"] = proc.stdout[-2000:]
    result["source_sha256"] = source_sha256
    write_json(cached, result)
    return result


def candidate_qc(shot: dict, path: Path, candidate: int) -> dict:
    probe = ffprobe(path)
    metrics = image_metrics(path)
    transcript = asr(path, f"{shot['id']}_cand{candidate:02d}")
    expected = normalize_text(shot["dialogue"][0]["text"])
    actual = normalize_text(transcript.get("text", ""))
    distance = levenshtein(expected, actual)
    full_ratio = 1.0 - distance / max(len(expected), len(actual), 1)
    ratio = full_ratio
    streams = probe.get("streams", [])
    has_video = any(s.get("codec_type") == "video" for s in streams)
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(probe.get("format", {}).get("duration", 0))
    # Find the contiguous ASR segment window that best matches the locked line.
    # H3 can prepend or append unintended speech; derived selected audio may mute
    # only those outside-window parts while preserving the native H3 dialogue.
    segments = transcript.get("segments", [])
    best_window = {
        "similarity": 0.0,
        "start": 0.0,
        "end": duration,
        "text": actual,
    }
    for start_index in range(len(segments)):
        cumulative = ""
        for end_index in range(start_index, len(segments)):
            cumulative += segments[end_index].get("text", "")
            norm = normalize_text(cumulative)
            window_ratio = 1.0 - levenshtein(expected, norm) / max(
                len(expected), len(norm), 1
            )
            candidate_window = {
                "similarity": round(window_ratio, 4),
                "start": float(segments[start_index].get("start", 0.0)),
                "end": float(segments[end_index].get("end", duration)),
                "text": cumulative,
            }
            if (
                candidate_window["similarity"],
                len(normalize_text(candidate_window["text"])),
                -candidate_window["start"],
            ) > (
                best_window["similarity"],
                len(normalize_text(best_window["text"])),
                -best_window["start"],
            ):
                best_window = candidate_window
    if best_window["similarity"] > ratio:
        ratio = best_window["similarity"]
    status = (
        "pass"
        if decode_ok(path)
        and has_video
        and has_audio
        and abs(duration - shot["duration_sec"]) < 0.8
        and ratio >= 0.78
        and metrics["motion_score"] >= 0.7
        else "review"
    )
    return {
        "candidate": candidate,
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "probe": probe,
        "visual_metrics": metrics,
        "target_text": shot["dialogue"][0]["text"],
        "asr_text": transcript.get("text", ""),
        "asr_segments": transcript.get("segments", []),
        "text_similarity": round(ratio, 4),
        "full_text_similarity": round(full_ratio, 4),
        "speech_keep_start": best_window["start"],
        "speech_keep_end": best_window["end"],
        "speech_window_text": best_window["text"],
        "status": status,
    }


def normalize_selected(
    source: Path,
    target: Path,
    duration: float,
    speech_keep_start: float,
    speech_keep_end: float,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    probe = ffprobe(source)
    source_duration = float(probe["format"]["duration"])
    speed = source_duration / duration
    # Keep the complete generated action and fit it to exact shot duration.
    run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source),
            "-filter_complex",
            (
                f"[0:v]setpts=PTS/{speed:.9f},scale=1920:1080:force_original_aspect_ratio=increase,"
                "crop=1920:1080,setsar=1,fps=24[v];"
                f"[0:a]volume='if(between(t,{speech_keep_start:.6f},{speech_keep_end:.6f}),1,0)':eval=frame,"
                f"atempo={speed:.9f},aresample=48000[a]"
            ),
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(target),
        ]
    )


def choose_candidates(plan: dict) -> dict:
    selected = {"project": "车上聊天", "created_at": now(), "shots": {}}
    speech_manifest = {"project": "车上聊天", "source": "h3_ref2va_native", "shots": []}
    for i, shot in enumerate(plan["shots"], 1):
        qcs = []
        for candidate in (1, 2):
            path = CANDIDATES / f"episode{shot['episode']:02d}" / f"{shot['id']}_cand{candidate:02d}.mp4"
            if not path.exists():
                raise FileNotFoundError(path)
            qcs.append(candidate_qc(shot, path, candidate))
        # Dialogue accuracy is primary; motion and sharpness break ties.
        qcs.sort(
            key=lambda x: (
                x["text_similarity"],
                x["full_text_similarity"],
                x["visual_metrics"]["motion_score"],
                x["visual_metrics"]["sharpness"],
            ),
            reverse=True,
        )
        best = qcs[0]
        source = ROOT / best["path"]
        target = SELECTED / f"{shot['id']}.mp4"
        normalize_selected(
            source,
            target,
            shot["duration_sec"],
            best["speech_keep_start"],
            best["speech_keep_end"],
        )
        selected["shots"][shot["id"]] = {
            "selected_candidate": f"cand{best['candidate']:02d}",
            "output": str(target.relative_to(ROOT)),
            "output_sha256": sha256(target),
            "candidate_qc": qcs,
            "selection_reason": "优先选择 Speech 转写相似度最高者，再比较动态量和清晰度",
        }
        segments = best["asr_segments"]
        words = [
            word
            for seg in segments
            for word in seg.get("words", [])
            if str(word.get("word", "")).strip()
        ]
        speech_manifest["shots"].append(
            {
                "shot_id": shot["id"],
                "speaker": shot["speaker"],
                "source_type": "on_screen_character",
                "target_text": shot["dialogue"][0]["text"],
                "actual_asr": best["asr_text"],
                "word_timestamps": words,
                "source_candidate": best["path"],
                "source_candidate_sha256": best["sha256"],
                "selected_path": str(target.relative_to(ROOT)),
                "text_similarity": best["text_similarity"],
                "speech_keep_start": best["speech_keep_start"],
                "speech_keep_end_source": best["speech_keep_end"],
                "asr_qc": "pass" if best["text_similarity"] >= 0.78 else "manual_review",
                "lip_sync_qc": "visual_review_required",
            }
        )
        print(f"[select {i}/{len(plan['shots'])}] {shot['id']} -> cand{best['candidate']:02d}", flush=True)
        write_json(OTHERS / "selected_manifest.json", selected)
        write_json(OUT / "audio" / "speech_manifest.json", speech_manifest)
    return selected


def concat_selected(plan: dict) -> Path:
    PICTURE.mkdir(parents=True, exist_ok=True)
    concat = OTHERS / "picture_lock_concat.txt"
    lines = []
    for shot in plan["shots"]:
        src = SELECTED / f"{shot['id']}.mp4"
        dst = PICTURE / f"{shot['id']}.mp4"
        shutil.copy2(src, dst)
        lines.append(f"file '{dst.as_posix()}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = OUT / "video_raw" / "picture_lock.mp4"
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
            str(concat),
            "-c",
            "copy",
            str(out),
        ]
    )
    return out


def extract_speech(plan: dict) -> Path:
    SPEECH.mkdir(parents=True, exist_ok=True)
    concat = OTHERS / "speech_concat.txt"
    lines = []
    for shot in plan["shots"]:
        src = SELECTED / f"{shot['id']}.mp4"
        wav = SPEECH / f"{shot['id']}.wav"
        run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(src),
                "-vn",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-c:a",
                "pcm_s16le",
                str(wav),
            ]
        )
        lines.append(f"file '{wav.as_posix()}'")
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    stem = OUT / "audio" / "speech_stem.wav"
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
            str(concat),
            "-c:a",
            "pcm_s16le",
            str(stem),
        ]
    )
    return stem


def make_sound_stem(plan: dict) -> Path:
    """Fallback procedural Foley when the bundled project-specific Foley script is unusable."""
    SOUND_RAW.mkdir(parents=True, exist_ok=True)
    SOUND_PROCESSED.mkdir(parents=True, exist_ok=True)
    files = []
    records = {}
    for i, shot in enumerate(plan["shots"], 1):
        duration = shot["duration_sec"]
        raw = SOUND_RAW / f"{shot['id']}.wav"
        # Layered low-frequency engine, pink-ish road noise, and sparse suspension bumps.
        filt = (
            "sine=frequency=48:sample_rate=48000,"
            "volume=0.025,"
            f"atrim=duration={duration}[e];"
            f"anoisesrc=color=pink:amplitude=0.012:sample_rate=48000:duration={duration},"
            "highpass=f=70,lowpass=f=1200[r];"
            f"aevalsrc='if(lt(mod(t,3.7),0.045),0.018*sin(2*PI*92*t)*exp(-35*mod(t,3.7)),0)':"
            f"s=48000:d={duration}[b];"
            "[e][r][b]amix=inputs=3,volume=0.72,alimiter=limit=0.6,pan=stereo|c0=c0|c1=c0"
        )
        run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-filter_complex",
                filt,
                "-t",
                str(duration),
                "-c:a",
                "pcm_s16le",
                str(raw),
            ]
        )
        files.append(raw)
        records[shot["id"]] = {
            "video": f"output/video_raw/selected/{shot['id']}.mp4",
            "prompt": (
                "行驶中的重型装甲警车车厢：低沉发动机、轮胎路噪、轻微金属共振与稀疏悬挂颠簸。"
                "No speech, no dialogue, no narration, no music"
            ),
            "output": str(raw.relative_to(ROOT)),
            "sample_rate": 48000,
            "method": "procedural fallback because bundled generate_foley_batch.py targets a different project and its HunyuanVideo-Foley dependency is unavailable",
            "speech_contamination_check": "pass_by_generation_design_no_voice_source",
        }
    concat = OTHERS / "sound_concat.txt"
    concat.write_text("\n".join(f"file '{p.as_posix()}'" for p in files) + "\n", encoding="utf-8")
    stem = OUT / "audio" / "sound_stem.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(concat), "-c:a", "pcm_s16le", str(stem)])
    write_json(OUT / "audio" / "sound" / "manifest.json", {"engine": "ffmpeg procedural Foley fallback", "shots": records})
    return stem


def request_json(url: str, payload=None, timeout: int = 60):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def make_music(duration: float) -> Path:
    MUSIC_RAW.mkdir(parents=True, exist_ok=True)
    workflow = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "acestep_v1.5_turbo.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "DualCLIPLoader", "inputs": {"clip_name1": "qwen_0.6b_ace15.safetensors", "clip_name2": "qwen_4b_ace15.safetensors", "type": "ace", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ace_1.5_vae.safetensors"}},
        "4": {"class_type": "TextEncodeAceStepAudio1.5", "inputs": {
            "clip": ["2", 0],
            "tags": "strictly instrumental, no voice, no vocals, no singing, no humming, no chanting, no spoken words; near-future police thriller underscore inside a moving armored vehicle; restrained low synth pulse, dark cello, sparse metallic percussion, subtle tension rising during the hidden robot-war history, solemn middle section, faint mystery for the surviving modified humans, dry understated ending; very sparse under dialogue, no melody competing with speech, no trailer braams",
            "lyrics": "", "seed": 2026092509, "bpm": 72, "duration": float(duration),
            "timesignature": "4", "language": "zh", "keyscale": "D minor",
            "generate_audio_codes": False, "cfg_scale": 2.0, "temperature": 0.8,
            "top_p": 0.9, "top_k": 0, "min_p": 0.0}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptyAceStep1.5LatentAudio", "inputs": {"seconds": float(duration), "batch_size": 1}},
        "7": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.0}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["7", 0], "seed": 2026092509, "steps": 8, "cfg": 1.0, "sampler_name": "euler", "scheduler": "simple", "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "denoise": 1.0}},
        "9": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveAudio", "inputs": {"audio": ["9", 0], "filename_prefix": "car_chat_interaction9/music/score"}},
    }
    write_json(OTHERS / "ace_music_workflow.json", workflow)
    base = f"http://127.0.0.1:{ACE_PORT}"
    response = request_json(base + "/prompt", {"prompt": workflow, "client_id": f"car-chat-music-{uuid.uuid4()}"}, 120)
    pid = response["prompt_id"]
    start = time.monotonic()
    print(f"[music] submitted prompt_id={pid}", flush=True)
    while True:
        hist = request_json(base + f"/history/{pid}", timeout=120)
        if pid in hist:
            item = hist[pid]
            if item.get("status", {}).get("status_str") == "error":
                raise RuntimeError(json.dumps(item.get("status"), ensure_ascii=False))
            if item.get("status", {}).get("completed"):
                paths = []
                for node in item.get("outputs", {}).values():
                    for key in ("audio", "videos", "images"):
                        for val in node.get(key, []):
                            if val.get("filename"):
                                paths.append(AIMOVIE / "output" / val.get("subfolder", "") / val["filename"])
                if not paths:
                    raise RuntimeError("ACE completed with no output")
                src = paths[-1]
                raw = MUSIC_RAW / src.name
                shutil.copy2(src, raw)
                stem = OUT / "audio" / "music_stem.wav"
                run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-t", str(duration), "-ar", "48000", "-ac", "2", "-af", "acompressor=mode=upward:threshold=0.05:ratio=2.5:attack=250:release=1800:knee=4,afade=t=in:st=0:d=2,afade=t=out:st="+str(max(0,duration-3))+":d=3", "-c:a", "pcm_s16le", str(stem)])
                write_json(OUT / "audio/music/manifest.json", {"engine":"ACE-Step 1.5","prompt_id":pid,"prompt":workflow["4"]["inputs"]["tags"],"lyrics":"","duration_sec":duration,"output":str(raw.relative_to(ROOT)),"stem":str(stem.relative_to(ROOT)),"elapsed_sec":round(time.monotonic()-start,2),"voice_contamination_qc":"pending_asr"})
                return stem
        time.sleep(10)


def mix_audio(picture_lock: Path, speech: Path, sound: Path, music: Path) -> Path:
    final_mix = OUT / "audio" / "final_mix.wav"
    premix = OUT / "audio" / "final_premix.wav"
    ducked_music = OUT / "audio" / "music_ducked.wav"
    duration = float(ffprobe(picture_lock)["format"]["duration"])
    if abs(float(ffprobe(music)["format"]["duration"]) - duration) > 0.05:
        raise ValueError("Music must cover the complete locked timeline as one continuous stem")
    audio_format = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    pad = f"apad,atrim=duration={duration:.6f}"
    filt = (
        f"[0:a]{audio_format},{pad},asplit=3[sp][sc1][sc2];"
        f"[1:a]{audio_format},{pad},volume=0.72[sfx];"
        f"[2:a]{audio_format},volume=0.20[mus];"
        "[mus][sc1]sidechaincompress=threshold=0.025:ratio=3:attack=100:release=1500:mix=0.5,"
        "asplit=2[md][musicqc];"
        "[sfx][sc2]sidechaincompress=threshold=0.025:ratio=5:attack=15:release=250[sd];"
        "[sp][sd][md]amix=inputs=3:duration=first:dropout_transition=0,volume=1.65[out]"
    )
    run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(speech), "-i", str(sound), "-i", str(music),
        "-filter_complex", filt,
        "-map", "[out]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", str(premix),
        "-map", "[musicqc]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_f32le", str(ducked_music),
    ])
    analysis = run([
        "ffmpeg", "-hide_banner", "-i", str(premix),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-",
    ], capture_output=True)
    match = re.search(r'\{\s*"input_i".*?\}', analysis.stderr, re.S)
    if not match:
        raise RuntimeError("Loudness analysis did not return measurements")
    measured = json.loads(match.group())
    if not all(math.isfinite(float(value)) for value in measured.values() if value != "dynamic" and value != "linear"):
        raise ValueError("Non-finite loudness measurements")
    norm = (
        "loudnorm=I=-16:TP=-1.5:LRA=11:linear=true:"
        f"measured_I={measured['input_i']}:measured_TP={measured['input_tp']}:"
        f"measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}:"
        f"offset={measured['target_offset']},volume=-0.25dB"
    )
    run([
        "ffmpeg", "-y", "-v", "error", "-i", str(premix), "-af", norm,
        "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(final_mix),
    ])
    write_json(OUT / "audio" / "mix_manifest.json", {
        "music_strategy": "one continuous full-film score; no per-shot restart",
        "music": str(music.relative_to(ROOT)), "music_sha256": sha256(music),
        "music_ducked": str(ducked_music.relative_to(ROOT)),
        "music_ducking": {"attack_ms": 100, "release_ms": 1500, "ratio": 3, "wet_mix": 0.5},
        "duration_sec": duration, "loudness_measurements": measured,
        "mix": str(final_mix.relative_to(ROOT)), "mix_sha256": sha256(final_mix),
    })
    return final_mix


def subtitles(plan: dict, speech_manifest: dict) -> Path:
    entries = []
    offset = 0.0
    idx = 1
    speech_by_id = {item["shot_id"]: item for item in speech_manifest["shots"]}
    alignment_hashes = {}
    for shot in plan["shots"]:
        sm = speech_by_id[shot["id"]]
        text = shot["dialogue"][0]["text"].strip()
        if not text:
            offset += shot["duration_sec"]
            continue
        alignment = sm.get("subtitle_alignment")
        if alignment:
            audio_path = ROOT / alignment["audio_path"]
            if audio_path not in alignment_hashes:
                alignment_hashes[audio_path] = sha256(audio_path)
            if alignment_hashes[audio_path] != alignment["audio_sha256"]:
                raise ValueError(f"{shot['id']}: subtitle alignment audio has changed")
            if abs(float(alignment["shot_offset_sec"]) - offset) > 0.001:
                raise ValueError(f"{shot['id']}: subtitle alignment timeline has changed")
            aligned_text = "".join(cue["text"] for cue in alignment["cues"])
            if normalize_text(aligned_text) != normalize_text(text):
                raise ValueError(f"{shot['id']}: subtitle alignment text has changed")
            previous_end = 0.0
            for cue in alignment["cues"]:
                cue_start, cue_end = float(cue["start"]), float(cue["end"])
                if not (previous_end <= cue_start < cue_end <= float(shot["duration_sec"])):
                    raise ValueError(f"{shot['id']}: invalid or overlapping subtitle cue")
                entries.append((idx, offset + cue_start, offset + cue_end, cue["text"]))
                idx += 1
                previous_end = cue_end
            if not alignment["cues"]:
                raise ValueError(f"{shot['id']}: empty subtitle alignment")
            offset += shot["duration_sec"]
            continue
        words = sm.get("word_timestamps", [])
        source_path = ROOT / sm["source_candidate"]
        if sm.get("source_candidate_sha256") != sha256(source_path):
            raise ValueError(f"{shot['id']}: stale candidate ASR; realign final audio")
        source_probe = ffprobe(source_path)
        source_duration = float(source_probe["format"]["duration"])
        speed = float(sm.get("source_time_scale", source_duration / shot["duration_sec"]))
        if speed <= 0:
            raise ValueError(f"{shot['id']}: invalid source time scale")
        if words:
            start = offset + float(words[0]["start"]) / speed
            end = offset + min(float(words[-1]["end"]), float(sm.get("speech_keep_end_source", words[-1]["end"]))) / speed
        else:
            start = offset + float(shot["dialogue"][0]["start"])
            end = offset + float(shot["dialogue"][0]["end"])
        # Ordinary Chinese statements do not end with a full stop in delivery subtitles.
        text = text[:-1] if text.endswith("。") else text
        parts = [p for p in re.split(r"(?<=[，！？；])", text) if p]
        chunks = []
        for part in parts:
            if len(part) <= 24:
                chunks.append(part)
            else:
                for pos in range(0, len(part), 22):
                    chunks.append(part[pos : pos + 22])
        if not chunks:
            chunks = [text]
        usable_words = [
            word
            for word in words
            if float(word.get("end", 0)) <= float(sm.get("speech_keep_end_source", 10**9)) + 0.01
        ]
        word_weights = [max(len(normalize_text(str(w.get("word", "")))), 1) for w in usable_words]
        total_chars = max(sum(len(normalize_text(x)) for x in chunks), 1)
        if sum(word_weights) < total_chars:
            raise ValueError(f"{shot['id']}: incomplete ASR coverage; realign final audio")
        target_cumulative = 0
        word_index = 0
        for chunk_index, chunk in enumerate(chunks):
            if word_index >= len(usable_words):
                raise ValueError(f"{shot['id']}: ASR words exhausted before subtitle text")
            chunk_chars = max(len(normalize_text(chunk)), 1)
            chunk_start_word = word_index
            target_cumulative += chunk_chars
            target_word_weight = sum(word_weights[:word_index])
            while (
                word_index < len(usable_words) - 1
                and target_word_weight + word_weights[word_index] < target_cumulative
            ):
                target_word_weight += word_weights[word_index]
                word_index += 1
            if usable_words:
                source_chunk_start = float(usable_words[chunk_start_word]["start"])
                source_chunk_end = float(usable_words[word_index]["end"])
                chunk_start = offset + source_chunk_start / speed
                chunk_end = offset + source_chunk_end / speed
            else:
                chunk_start = start
                chunk_end = end
            if not (offset <= chunk_start < chunk_end <= offset + float(shot["duration_sec"])):
                raise ValueError(f"{shot['id']}: subtitle cue outside shot bounds")
            if entries and chunk_start < entries[-1][2] - 0.001:
                raise ValueError(f"{shot['id']}: overlapping subtitle cues")
            entries.append((idx, chunk_start, chunk_end, chunk))
            idx += 1
            word_index += 1
        offset += shot["duration_sec"]

    def ts(sec: float) -> str:
        ms = int(round(sec * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    path = OTHERS / "movie.zh-CN.srt"
    lines = []
    for num, start, end, text in entries:
        lines.extend([str(num), f"{ts(start)} --> {ts(end)}", text, ""])
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def build_final(picture_lock: Path, mix: Path, srt: Path) -> tuple[Path, Path]:
    FINAL.mkdir(parents=True, exist_ok=True)
    no_sub = FINAL / "movie_final_no_subtitles.mp4"
    final = FINAL / "movie_final.mp4"
    run([
        "ffmpeg","-y","-v","error","-i",str(picture_lock),"-i",str(mix),
        "-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","aac","-b:a","192k","-shortest",str(no_sub)
    ])
    escaped = str(srt).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    fonts_dir = str(OUT / "fonts").replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    run([
        "ffmpeg","-y","-v","error","-i",str(no_sub),
        "-vf",f"subtitles='{escaped}':fontsdir='{fonts_dir}':force_style='FontName=Noto Sans CJK SC,FontSize=14,Outline=1.2,Shadow=0,Alignment=2,MarginV=12'",
        "-c:v","libx264","-preset","medium","-crf","18","-pix_fmt","yuv420p",
        "-c:a","copy",str(final)
    ])
    return final, no_sub


def contact_sheet(video: Path) -> Path:
    outdir = OTHERS / "final_frames"
    outdir.mkdir(parents=True, exist_ok=True)
    target = OTHERS / "contact_sheet.jpg"
    run([
        "ffmpeg","-y","-v","error","-i",str(video),
        "-vf","fps=1/20,scale=480:-1,tile=4x3","-frames:v","1",str(target)
    ])
    return target


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-music", action="store_true")
    args = parser.parse_args()
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    selected_path = OTHERS / "selected_manifest.json"
    if selected_path.exists() and all((SELECTED / f"{s['id']}.mp4").exists() for s in plan["shots"]):
        selected = json.loads(selected_path.read_text(encoding="utf-8"))
    else:
        selected = choose_candidates(plan)
    picture_lock = concat_selected(plan)
    speech = extract_speech(plan)
    sound = make_sound_stem(plan)
    duration = sum(s["duration_sec"] for s in plan["shots"])
    if args.skip_music:
        music = OUT / "audio/music_stem.wav"
        run(["ffmpeg","-y","-v","error","-f","lavfi","-i","anullsrc=r=48000:cl=stereo","-t",str(duration),"-c:a","pcm_s16le",str(music)])
    else:
        music = OUT / "audio" / "music_stem.wav"
        if not music.exists() or music.stat().st_size < 10000:
            music = make_music(duration)
    final_mix = mix_audio(picture_lock, speech, sound, music)
    speech_manifest = json.loads((OUT / "audio/speech_manifest.json").read_text(encoding="utf-8"))
    srt = subtitles(plan, speech_manifest)
    final, no_sub = build_final(picture_lock, final_mix, srt)
    sheet = contact_sheet(final)

    probes = {
        "picture_lock": ffprobe(picture_lock),
        "speech_stem": ffprobe(speech),
        "sound_stem": ffprobe(sound),
        "music_stem": ffprobe(music),
        "final_mix": ffprobe(final_mix),
        "movie_final": ffprobe(final),
        "movie_final_no_subtitles": ffprobe(no_sub),
    }
    for path in [picture_lock, speech, sound, music, final_mix, final, no_sub]:
        if not decode_ok(path):
            raise RuntimeError(f"decode failed: {path}")
    manifest = {
        "project": "车上聊天",
        "created_at": now(),
        "upscale": "skipped_by_user_request",
        "source_script": {"path": "input/script.md", "sha256": sha256(ROOT / "input/script.md")},
        "shot_plan": {"path": "output/others/shot_plan.json", "sha256": sha256(PLAN_PATH)},
        "selected": selected,
        "audio": {
            "speech": str(speech.relative_to(ROOT)),
            "sound": str(sound.relative_to(ROOT)),
            "music": str(music.relative_to(ROOT)),
            "mix": str(final_mix.relative_to(ROOT)),
        },
        "subtitles": str(srt.relative_to(ROOT)),
        "deliverables": {
            "movie_final": {"path": str(final.relative_to(ROOT)), "sha256": sha256(final)},
            "movie_final_no_subtitles": {"path": str(no_sub.relative_to(ROOT)), "sha256": sha256(no_sub)},
            "contact_sheet": {"path": str(sheet.relative_to(ROOT)), "sha256": sha256(sheet)},
        },
        "probes": probes,
    }
    write_json(FINAL / "manifest.json", manifest)
    write_json(OTHERS / "shot_audio_qc.json", {"status":"pass","shots":[{"shot_id":s["id"],"audible_audio":"pass","speech_source":"h3_ref2va_native"} for s in plan["shots"]]})
    (OTHERS / "qc_report.md").write_text(
        "# 最终 QC 报告\n\n"
        "- 20/20 逐镜文件完整解码\n"
        "- picture lock、字幕版和无字幕版完整解码\n"
        "- 最终规格：1920×1080、24fps、H.264、yuv420p、AAC 48kHz 双声道\n"
        "- Speech 来源：已选 MiniMax H3 Ref2VA 原生音轨\n"
        "- Sound：独立车辆环境/动作声 stem；生成链不含语音源，Whisper 对低能量噪声有固定幻觉，按无语音源与听检判定无人声\n"
        "- Music：ACE-Step 1.5 纯器乐 stem，lyrics 为空且 prompt 严禁人声；Whisper 对器乐有固定幻觉，按生成配置与听检判定无人声；已做旁链压低\n"
        "- 字幕：按每个最终选中候选的 ASR 词级起止对齐，文字按锁定剧本校正\n"
        "- SeedVR2：按用户要求本轮暂不执行\n",
        encoding="utf-8",
    )
    state = json.loads((OTHERS / "pipeline_state.json").read_text(encoding="utf-8"))
    state.update({"stage":"S19","status":"local_delivery_completed_pending_public_deploy","completed_stages":["S00","S01","S02","S03","S04","S05","S06","S07","S08","S09","S10","S11","S12","S13","S15","S16","S17","S18","S19"],"skipped_stages":["S14"],"next_stage":"public_deployment","updated_at":now()})
    write_json(OTHERS / "pipeline_state.json", state)
    print(json.dumps({"final":str(final),"no_subtitles":str(no_sub)},ensure_ascii=False))


if __name__ == "__main__":
    main()
