"""Moteur audio — pygame.mixer avec contrôle complet."""
from __future__ import annotations
import threading, time
from pathlib import Path
from typing import Callable

import pygame

class AudioEngine:
    def __init__(self) -> None:
        pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
        pygame.mixer.init()
        self._lock = threading.Lock()
        self._path: str = ""
        self._length: float = 0.0      # secondes
        self._start_time: float = 0.0  # time.monotonic() au moment du play
        self._pause_pos: float = 0.0   # position en secondes au moment du pause
        self._paused: bool = False
        self._playing: bool = False
        self._volume: float = 0.8
        self._on_end: Callable[[], None] | None = None
        self._watch_thread: threading.Thread | None = None
        pygame.mixer.music.set_volume(self._volume)

    # ── Public ────────────────────────────────────────────────────────────────

    def load(self, path: str) -> None:
        with self._lock:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            self._path = path
            self._length = self._detect_length(path)
            self._paused = False
            self._playing = False
            self._start_time = 0.0
            self._pause_pos = 0.0

    def play(self, from_pos: float = 0.0) -> None:
        with self._lock:
            pygame.mixer.music.play(start=from_pos)
            self._start_time = time.monotonic() - from_pos
            self._paused = False
            self._playing = True
        self._start_watch()

    def pause(self) -> None:
        with self._lock:
            if not self._playing or self._paused:
                return
            pygame.mixer.music.pause()
            self._pause_pos = self.position
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            if not self._paused:
                return
            pygame.mixer.music.unpause()
            self._start_time = time.monotonic() - self._pause_pos
            self._paused = False

    def stop(self) -> None:
        with self._lock:
            pygame.mixer.music.stop()
            self._playing = False
            self._paused = False
            self._pause_pos = 0.0

    def seek(self, seconds: float) -> None:
        with self._lock:
            pygame.mixer.music.play(start=seconds)
            self._start_time = time.monotonic() - seconds
            self._paused = False
            self._playing = True

    def set_volume(self, vol: float) -> None:
        self._volume = max(0.0, min(1.0, vol))
        pygame.mixer.music.set_volume(self._volume)

    def on_end(self, callback: Callable[[], None]) -> None:
        self._on_end = callback

    @property
    def position(self) -> float:
        if self._paused:
            return self._pause_pos
        if not self._playing:
            return 0.0
        return max(0.0, time.monotonic() - self._start_time)

    @property
    def length(self) -> float:
        return self._length

    @property
    def is_playing(self) -> bool:
        return self._playing and not self._paused

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def volume(self) -> float:
        return self._volume

    # ── Private ───────────────────────────────────────────────────────────────

    def _start_watch(self) -> None:
        if self._watch_thread and self._watch_thread.is_alive():
            return
        self._watch_thread = threading.Thread(target=self._watch_end, daemon=True)
        self._watch_thread.start()

    def _watch_end(self) -> None:
        while True:
            time.sleep(0.3)
            with self._lock:
                if not self._playing or self._paused:
                    break
                if not pygame.mixer.music.get_busy():
                    self._playing = False
                    break
        if self._on_end:
            self._on_end()

    @staticmethod
    def _detect_length(path: str) -> float:
        try:
            import mutagen
            f = mutagen.File(path)
            if f and hasattr(f.info, "length"):
                return float(f.info.length)
        except Exception:
            pass
        return 0.0
