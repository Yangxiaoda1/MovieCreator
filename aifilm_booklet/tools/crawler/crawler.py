#!/usr/bin/env python3
"""Download an authorized Bilibili or Xiaohongshu video.

Default source:
    https://www.bilibili.com/video/BV1KBafz5EZG/?p=1

Default output directory:
    <PROJECT_ROOT>/input/others

Usage:
    python crawler.py
    python crawler.py --audio-only
    python crawler.py --cookies /path/to/bilibili_cookies.txt --audio-only
    python crawler.py --cookies-from-browser chrome --audio-only
    python crawler.py --url https://www.bilibili.com/video/BV... --output-dir /path/to/save
    python crawler.py --url https://www.xiaohongshu.com/explore/... --output-dir /path/to/save
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_URL = "https://www.bilibili.com/video/BV1KBafz5EZG/?p=1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "input" / "others"
DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)


def find_ytdlp_command() -> list[str]:
    if shutil.which("yt-dlp"):
        return ["yt-dlp"]

    try:
        subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return [sys.executable, "-m", "yt_dlp"]
    except subprocess.CalledProcessError:
        pass

    raise RuntimeError(
        "未找到 yt-dlp。请先安装：python -m pip install -U yt-dlp"
    )


def is_xiaohongshu_url(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return "xiaohongshu.com" in host or "xhslink.com" in host


def request_headers(url: str) -> dict[str, str]:
    if is_xiaohongshu_url(url):
        return {
            "User-Agent": MOBILE_USER_AGENT,
            "Referer": "https://www.xiaohongshu.com/",
            "Origin": "https://www.xiaohongshu.com",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    return {
        "User-Agent": DESKTOP_USER_AGENT,
        "Referer": "https://www.bilibili.com/",
        "Origin": "https://www.bilibili.com",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def resolve_b23_url(url: str) -> str:
    if "b23.tv/" not in url:
        return url

    headers = request_headers("https://www.bilibili.com/")
    headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            resolved_url = response.geturl()
    except urllib.error.URLError as exc:
        print(f"短链解析失败，继续交给 yt-dlp 处理：{exc}", file=sys.stderr)
        return url

    if resolved_url != url:
        print(f"短链已解析为：{resolved_url}")
    return resolved_url


def resolve_xhs_url(url: str) -> str:
    if "xhslink.com" not in urllib.parse.urlparse(url).netloc.lower():
        return url

    request = urllib.request.Request(url, headers=request_headers(url))
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            resolved_url = response.geturl()
    except urllib.error.URLError as exc:
        print(f"小红书短链解析失败：{exc}", file=sys.stderr)
        return url

    if resolved_url != url:
        print(f"小红书短链已解析为：{resolved_url}")
    return resolved_url


def decode_escaped_url(url: str) -> str:
    return url.encode("utf-8").decode("unicode_escape").replace("\\/", "/")


def extract_xhs_video_url(page_text: str) -> str:
    patterns = (
        r'"masterUrl":"(http:[^"]+?\.mp4\?[^"\\]+)',
        r'"master_url":"(http:[^"]+?\.mp4\?[^"\\]+)',
        r'\\"master_url\\":\\"(http:[^\\"]+?\.mp4\?[^\\"]+)',
    )
    urls: list[str] = []
    for pattern in patterns:
        for match in re.findall(pattern, page_text):
            video_url = decode_escaped_url(match)
            if video_url not in urls:
                urls.append(video_url)

    if not urls:
        raise RuntimeError("未在小红书页面中找到可下载视频地址")
    return urls[0]


def xhs_note_id(url: str) -> str:
    parts = [part for part in urllib.parse.urlparse(url).path.split("/") if part]
    return parts[-1] if parts else "video"


def download_xiaohongshu_direct(args: argparse.Namespace) -> int:
    if args.audio_only:
        raise RuntimeError("小红书直链下载暂不支持 --audio-only，请先下载视频后用 ffmpeg 提取音频")
    if args.proxy:
        raise RuntimeError("小红书直链下载暂不支持 --proxy")

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    page_url = resolve_xhs_url(args.url)
    headers = request_headers(page_url)
    page_request = urllib.request.Request(page_url, headers=headers)
    with urllib.request.urlopen(page_request, timeout=20) as response:
        page_text = response.read().decode("utf-8", "replace")

    video_url = extract_xhs_video_url(page_text)
    output_path = output_dir / f"xiaohongshu_{xhs_note_id(page_url)}.mp4"
    video_request = urllib.request.Request(video_url, headers=headers)
    with urllib.request.urlopen(video_request, timeout=60) as response, output_path.open("wb") as file:
        downloaded = 0
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            file.write(chunk)
            downloaded += len(chunk)

    if downloaded <= 0:
        raise RuntimeError("小红书视频下载结果为空")
    print(f"已保存：{output_path} ({downloaded} bytes)")
    return 0


def build_command(args: argparse.Namespace) -> list[str]:
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    download_url = resolve_b23_url(args.url)

    headers = request_headers(download_url)
    output_template = str(output_dir / "%(title).200B-%(id)s.%(ext)s")
    cmd = [
        *find_ytdlp_command(),
        "--no-playlist",
        "--restrict-filenames",
        "--force-ipv4",
        "--extractor-retries",
        "5",
        "--fragment-retries",
        "10",
        "--user-agent",
        headers["User-Agent"],
        "--referer",
        headers["Referer"],
        "--add-header",
        f"Origin:{headers['Origin']}",
        "--add-header",
        f"Accept-Language:{headers['Accept-Language']}",
        "--merge-output-format",
        "mp4",
        "-o",
        output_template,
    ]

    if args.cookies:
        cmd.extend(["--cookies", str(Path(args.cookies).expanduser().resolve())])
    if args.cookies_from_browser:
        cmd.extend(["--cookies-from-browser", args.cookies_from_browser])
    if args.proxy:
        cmd.extend(["--proxy", args.proxy])

    if args.audio_only:
        cmd.extend([
            "-f",
            "bestaudio/best",
            "--extract-audio",
            "--audio-format",
            args.audio_format,
            "--audio-quality",
            "0",
        ])
    else:
        cmd.extend(["-f", args.format])

    cmd.append(download_url)
    return cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download an authorized Bilibili or Xiaohongshu video."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Bilibili, b23, Xiaohongshu or xhslink URL")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to save downloaded files",
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Extract audio only instead of downloading the video",
    )
    parser.add_argument(
        "--audio-format",
        default="mp3",
        choices=("mp3", "m4a", "wav", "flac", "opus"),
        help="Audio format used with --audio-only",
    )
    parser.add_argument(
        "--cookies",
        help="Netscape-format cookies.txt exported from a logged-in Bilibili browser session",
    )
    parser.add_argument(
        "--cookies-from-browser",
        help="Read cookies from a local browser, e.g. chrome, chromium, firefox, edge",
    )
    parser.add_argument(
        "--proxy",
        help="Optional proxy URL passed to yt-dlp, e.g. http://127.0.0.1:7890",
    )
    parser.add_argument(
        "--format",
        default="bv*+ba/best",
        help="yt-dlp format selector for video download",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if is_xiaohongshu_url(args.url):
        try:
            return download_xiaohongshu_direct(args)
        except RuntimeError as exc:
            print(f"小红书直链下载失败，改用 yt-dlp 尝试：{exc}", file=sys.stderr)

    try:
        cmd = build_command(args)
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        return 1

    print("执行命令：", " ".join(cmd))
    completed = subprocess.run(cmd)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
