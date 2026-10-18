#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import tempfile
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
NOTES = ROOT / "review_notes.json"


def read_notes() -> dict:
    try:
        data = json.loads(NOTES.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            if isinstance(data.get("notes"), dict):
                return data
            return {"notes": data, "updatedAt": 0, "updatedBy": ""}
    except Exception:
        pass
    return {"notes": {}, "updatedAt": 0, "updatedBy": ""}


def write_notes(payload: dict) -> None:
    NOTES.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix="review_notes.", suffix=".json", dir=NOTES.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(name, NOTES)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path == "/healthz":
            return self.send_json(200, {"status": "ok", "service": "storyboard-review"})
        if path == "/api/review-notes":
            return self.send_json(200, read_notes())
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path != "/api/review-notes":
            return self.send_json(404, {"ok": False, "error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length) or b"{}")
            key = str(body.get("key", "")).strip()
            if not key or len(key) > 200:
                raise ValueError("invalid key")
            doc = read_notes()
            doc.setdefault("notes", {})[key] = str(body.get("value", ""))[:20000]
            import time
            doc["updatedAt"] = int(time.time() * 1000)
            doc["updatedBy"] = str(body.get("updatedBy", "local-reviewer"))[:120]
            write_notes(doc)
            return self.send_json(200, {"ok": True, "key": key, "updatedAt": doc["updatedAt"]})
        except Exception as exc:
            return self.send_json(400, {"ok": False, "error": str(exc)})


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    host = os.environ.get("VIS_HOST", "0.0.0.0")
    port = int(os.environ.get("VIS_PORT", "18080"))
    print(f"Storyboard review: http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    main()
