"""Education videos stored on this clinic computer and shared by an unguessable link."""

from __future__ import annotations

import json
import re
import secrets
import socket
from pathlib import Path

from fastapi import HTTPException

from app.core.config import settings

MAX_BYTES = 80 * 1024 * 1024
ALLOWED = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}
TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,80}$")


def video_dir() -> Path:
    folder = Path(__file__).resolve().parents[2] / "uploads" / "education"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def share_origin() -> str:
    configured = (getattr(settings, "public_base_url", "") or "").strip().rstrip("/")
    if configured:
        return configured
    ip = "127.0.0.1"
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        ip = probe.getsockname()[0] or ip
    except OSError:
        pass
    finally:
        probe.close()
    return f"http://{ip}:8000"


def save_video(original_name: str, chunks, title: str) -> dict:
    ext = Path(original_name or "").suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(status_code=400, detail="Upload an mp4, webm, or mov video")
    token = secrets.token_urlsafe(18)
    dest = video_dir() / f"{token}{ext}"
    size = 0
    try:
        with dest.open("wb") as handle:
            for chunk in chunks:
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(status_code=400, detail="Video must be under 80 MB")
                handle.write(chunk)
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    if size < 1000:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="That video file is empty")
    label = (title or Path(original_name).stem or "Education video").strip()[:120]
    meta = {"title": label, "original": Path(original_name).name, "ext": ext, "bytes": size}
    (video_dir() / f"{token}.json").write_text(json.dumps(meta), encoding="utf-8")
    return {
        "token": token,
        "title": label,
        "bytes": size,
        "url": f"{share_origin()}/api/v1/messages/videos/{token}",
    }


def resolve_video(token: str) -> tuple[Path, str, str]:
    if not TOKEN.match(token or ""):
        raise HTTPException(status_code=404, detail="Video not found")
    meta_path = video_dir() / f"{token}.json"
    if not meta_path.is_file():
        raise HTTPException(status_code=404, detail="Video not found")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    ext = meta.get("ext") if meta.get("ext") in ALLOWED else ""
    path = (video_dir() / f"{token}{ext}").resolve()
    if video_dir().resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="Video not found")
    return path, ALLOWED[ext], meta.get("title") or "video"
