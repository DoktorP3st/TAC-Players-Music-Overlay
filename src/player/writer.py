"""Écrit now_playing.json et copie la cover pour l'overlay OBS."""
from __future__ import annotations
import json, shutil, time
from pathlib import Path
from src.core.config import data_dir

def write_now_playing(
    title: str,
    artist: str,
    album: str,
    duration: float,
    position: float,
    playing: bool,
    cover_src: str | None,
    shuffle: bool,
    repeat: str,
    track_id: int = 0,
) -> None:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)

    # Copie la cover
    cover_dest = d / "cover.jpg"
    if cover_src and Path(cover_src).exists():
        try:
            _copy_cover(cover_src, cover_dest)
        except Exception:
            pass
    elif not cover_dest.exists():
        _write_placeholder(cover_dest)

    payload = {
        "playing":   playing,
        "title":     title,
        "artist":    artist,
        "album":     album,
        "duration":  round(duration, 2),
        "position":  round(position, 2),
        "timestamp": round(time.time(), 3),
        "progress":  round(position / duration, 4) if duration > 0 else 0,
        "shuffle":   shuffle,
        "repeat":    repeat,
        "track_id":  track_id,
    }
    tmp = d / "now_playing.tmp"
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / "now_playing.json")

def write_stopped() -> None:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    payload = {"playing": False, "title": "", "artist": "", "album": "",
               "duration": 0, "position": 0, "timestamp": round(time.time(), 3),
               "progress": 0, "shuffle": False, "repeat": "off"}
    tmp = d / "now_playing.tmp"
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(d / "now_playing.json")

def _copy_cover(src: str, dest: Path) -> None:
    from PIL import Image
    img = Image.open(src).convert("RGB")
    img.thumbnail((500, 500))
    img.save(dest, "JPEG", quality=90)

def _write_placeholder(dest: Path) -> None:
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (300, 300), "#1a1a1a")
        draw = ImageDraw.Draw(img)
        draw.text((150, 150), "♫", fill="#444444", anchor="mm")
        img.save(dest, "JPEG")
    except Exception:
        dest.write_bytes(b"")
