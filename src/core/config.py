"""Persistance configuration — AppData/Pestovich/Music Player Overlay"""
from __future__ import annotations
import json, os
from dataclasses import dataclass, field
from pathlib import Path

APP_VENDOR = "Pestovich"
APP_NAME   = "Music Player Overlay"

@dataclass
class AppConfig:
    folders: list[str]        = field(default_factory=list)   # dossiers ajoutés
    folder_artists: dict      = field(default_factory=dict)   # {folder_path: artist_name}
    queue: list[str]          = field(default_factory=list)
    queue_index: int          = 0
    volume: float             = 0.8
    shuffle: bool             = False
    repeat: str               = "off"          # "off" | "one" | "all"
    overlay_port: int         = 8080
    accent_color: str         = "#7c3aed"
    window_geometry: str      = "1120x700+80+80"

    # Overlay visual settings
    ov_opacity: float    = 0.82
    ov_blur: int         = 20
    ov_bg: str           = "#0a0a0a"
    ov_radius: int       = 16
    ov_width: int        = 420
    ov_accent: str       = "#7c3aed"
    ov_title_color: str  = "#f4f4f5"
    ov_artist_color: str = "#a78bfa"
    ov_title_size: int   = 15
    ov_artist_size: int  = 12
    ov_show_cover: bool  = True
    ov_show_progress: bool = True
    ov_transition: float = 0.3
    ov_theme: str        = "glassmorphism"

    def save(self) -> None:
        _path().parent.mkdir(parents=True, exist_ok=True)
        tmp = _path().with_suffix(".tmp")
        tmp.write_text(json.dumps(self.__dict__, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_path())

    @classmethod
    def load(cls) -> "AppConfig":
        try:
            data = json.loads(_path().read_text(encoding="utf-8"))
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except Exception:
            return cls()

def _path() -> Path:
    appdata = Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming")
    return appdata / APP_VENDOR / APP_NAME / "config.json"

def data_dir() -> Path:
    """Répertoire data/ à côté du dossier du projet (pour now_playing.json et cover.jpg)."""
    return Path(__file__).resolve().parents[2] / "data"
