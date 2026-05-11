"""Scan récursif de dossiers audio."""
from __future__ import annotations
from pathlib import Path

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aiff", ".aac"}
COVER_NAMES = {"cover.png", "cover.jpg", "cover.jpeg", "folder.jpg", "folder.png", "artwork.jpg", "artwork.png"}

def scan_folder(folder: str, recursive: bool = True) -> list[str]:
    """Retourne la liste des fichiers audio dans le dossier."""
    p = Path(folder)
    if not p.is_dir():
        return []
    pattern = "**/*" if recursive else "*"
    files = [str(f) for f in p.glob(pattern) if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS]
    return sorted(files)

def find_cover(audio_path: str) -> str | None:
    """Cherche une cover dans le même dossier que le fichier audio."""
    folder = Path(audio_path).parent
    for name in COVER_NAMES:
        candidate = folder / name
        if candidate.exists():
            return str(candidate)
    return None
