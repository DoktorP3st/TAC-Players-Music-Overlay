"""Interface de contrôle — customtkinter."""
from __future__ import annotations

import random
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from PIL import Image, ImageTk

from src.core.config import AppConfig
from src.core.scanner import scan_folder, find_cover
from src.player.engine import AudioEngine
from src.player.writer import write_now_playing, write_stopped

# ── Palette Pestovich ────────────────────────────────────────────────────────
BG     = "#0a0a0a"
SURF   = "#111111"
SURF2  = "#161616"
SURF3  = "#1e1e1e"
BORDER = "#252525"
ACCENT = "#7c3aed"
ACCHOV = "#6d28d9"
ACCLT  = "#a78bfa"
TEXT   = "#f4f4f5"
MUTED  = "#71717a"
SUCCESS= "#22c55e"
WARN   = "#f59e0b"
DANGER = "#ef4444"


def _read_meta(path: str) -> tuple[str, str, str]:
    """Retourne (title, artist, album) depuis mutagen ou nom de fichier."""
    try:
        from mutagen import File
        f = File(path, easy=True)
        if f:
            title  = str(f.get("title",  [Path(path).stem])[0])
            artist = str(f.get("artist", [""])[0])
            album  = str(f.get("album",  [""])[0])
            return title, artist, album
    except Exception:
        pass
    return Path(path).stem, "", ""


def _detect_duration(path: str) -> float:
    """Durée du fichier en secondes — plusieurs méthodes en fallback."""
    try:
        from mutagen import File
        f = File(path)
        if f and hasattr(f.info, "length"):
            return float(f.info.length)
    except Exception:
        pass
    try:
        import wave
        with wave.open(path, "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        pass
    return 0.0


class ControlPanel(ctk.CTk):
    def __init__(self, cfg: AppConfig, server) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.cfg    = cfg
        self.server = server
        self.engine = AudioEngine()
        self.engine.on_end(self._on_track_end)

        # État interne
        self._queue: list[str] = list(cfg.queue)
        self._index: int       = cfg.queue_index
        self._shuffle_order: list[int] = []
        self._seeking: bool    = False
        self._cover_img: ImageTk.PhotoImage | None = None
        self._meta_cache: dict[str, tuple[str, str, str, float]] = {}  # path → (title, artist, album, duration)
        self._track_id: int = 0   # incrémenté à chaque changement de titre

        self.title("Music Player Overlay")
        self.geometry(cfg.window_geometry)
        self.configure(fg_color=BG)
        self.resizable(True, True)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._refresh_queue_list()
        self._refresh_folder_list()
        self._tick()

    def _get_folder_artist(self, path: str) -> str:
        """Retourne l'artiste configuré pour le dossier du fichier, ou ''."""
        folder = Path(path).parent.resolve()
        for registered, artist in self.cfg.folder_artists.items():
            try:
                folder.relative_to(Path(registered).resolve())
                return artist
            except ValueError:
                pass
        return ""

    def _force_refresh(self) -> None:
        """Force l'écriture immédiate du JSON et signale le changement au bouton."""
        self._meta_cache.clear()
        self._write_state()
        self._refresh_btn.configure(text="✓ OK", text_color=SUCCESS)
        self.after(1200, lambda: self._refresh_btn.configure(text="🔄 Rafraîchir",
                                                              text_color=TEXT))

    def _cached_meta(self, path: str) -> tuple[str, str, str, float]:
        """Lit titre/artiste/album/durée avec cache. Applique l'override artiste si défini."""
        if path not in self._meta_cache:
            title, artist, album = _read_meta(path)
            duration = _detect_duration(path)
            self._meta_cache[path] = (title, artist, album, duration)
        title, artist, album, duration = self._meta_cache[path]
        override = self._get_folder_artist(path)
        if override:
            artist = override
        return title, artist, album, duration

    # ══════════════════════════════════════════════════════════════════════════
    #  BUILD UI
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0, minsize=220)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=280)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_queue_panel()
        self._build_now_playing()

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        sb = ctk.CTkFrame(self, fg_color=SURF, corner_radius=0, border_width=1,
                          border_color=BORDER)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_rowconfigure(2, weight=1)
        sb.grid_columnconfigure(0, weight=1)

        # Titre
        ctk.CTkLabel(sb, text="DOSSIERS", font=("Segoe UI", 10, "bold"),
                     text_color=MUTED).grid(row=0, column=0, padx=12, pady=(14, 4), sticky="w")

        # Liste dossiers
        self._folder_frame = ctk.CTkScrollableFrame(sb, fg_color=SURF2, corner_radius=8,
                                                     height=200)
        self._folder_frame.grid(row=1, column=0, padx=8, pady=4, sticky="ew")
        self._folder_frame.grid_columnconfigure(0, weight=1)

        # Spacer
        ctk.CTkFrame(sb, fg_color="transparent", height=1).grid(row=2, column=0, sticky="nsew")

        # Boutons
        btn_frame = ctk.CTkFrame(sb, fg_color="transparent")
        btn_frame.grid(row=3, column=0, padx=8, pady=4, sticky="ew")
        btn_frame.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(btn_frame, text="+ Dossier", fg_color=SURF3, hover_color=ACCENT,
                      text_color=TEXT, height=32, corner_radius=8,
                      command=self._add_folder).grid(row=0, column=0, padx=(0, 2), sticky="ew")
        ctk.CTkButton(btn_frame, text="+ Fichiers", fg_color=SURF3, hover_color=ACCENT,
                      text_color=TEXT, height=32, corner_radius=8,
                      command=self._add_files).grid(row=0, column=1, padx=(2, 0), sticky="ew")

        sep = ctk.CTkFrame(sb, fg_color=BORDER, height=1)
        sep.grid(row=4, column=0, padx=8, pady=8, sticky="ew")

        # Statut overlay
        ctk.CTkLabel(sb, text="OVERLAY", font=("Segoe UI", 10, "bold"),
                     text_color=MUTED).grid(row=5, column=0, padx=12, pady=(0, 4), sticky="w")

        self._status_dot = ctk.CTkLabel(sb, text="● Actif", text_color=SUCCESS,
                                        font=("Segoe UI", 12, "bold"))
        self._status_dot.grid(row=6, column=0, padx=12, pady=(0, 2), sticky="w")

        self._port_label = ctk.CTkLabel(sb, text=f"Port : {self.cfg.overlay_port}",
                                        text_color=MUTED, font=("Segoe UI", 11))
        self._port_label.grid(row=7, column=0, padx=12, pady=(0, 4), sticky="w")

        obs_btns = ctk.CTkFrame(sb, fg_color="transparent")
        obs_btns.grid(row=8, column=0, padx=8, pady=(0, 14), sticky="ew")
        obs_btns.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(obs_btns, text="Copier URL", fg_color=SURF3, hover_color=ACCENT,
                      text_color=TEXT, height=30, corner_radius=8,
                      command=self._copy_obs_url).grid(row=0, column=0, padx=(0, 2), sticky="ew")

        self._refresh_btn = ctk.CTkButton(obs_btns, text="🔄 Rafraîchir", fg_color=SURF3,
                                           hover_color=SUCCESS, text_color=TEXT,
                                           height=30, corner_radius=8,
                                           command=self._force_refresh)
        self._refresh_btn.grid(row=0, column=1, padx=(2, 0), sticky="ew")

    # ── Queue ─────────────────────────────────────────────────────────────────

    def _build_queue_panel(self) -> None:
        panel = ctk.CTkFrame(self, fg_color=SURF2, corner_radius=0,
                             border_width=1, border_color=BORDER)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(panel, fg_color="transparent")
        header.grid(row=0, column=0, padx=12, pady=(12, 4), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="FILE D'ATTENTE", font=("Segoe UI", 11, "bold"),
                     text_color=MUTED).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(header, text="Vider", fg_color=SURF3, hover_color=DANGER,
                      text_color=MUTED, height=24, width=60, corner_radius=6,
                      command=self._clear_queue).grid(row=0, column=1)

        self._queue_list = ctk.CTkScrollableFrame(panel, fg_color="transparent")
        self._queue_list.grid(row=1, column=0, padx=4, pady=4, sticky="nsew")
        self._queue_list.grid_columnconfigure(0, weight=1)

    # ── Now Playing ───────────────────────────────────────────────────────────

    def _build_now_playing(self) -> None:
        np = ctk.CTkFrame(self, fg_color=SURF, corner_radius=0,
                          border_width=1, border_color=BORDER)
        np.grid(row=0, column=2, sticky="nsew")
        np.grid_columnconfigure(0, weight=1)

        # Cover
        self._cover_label = ctk.CTkLabel(np, text="", width=200, height=200)
        self._cover_label.grid(row=0, column=0, padx=20, pady=(20, 10))
        self._set_placeholder_cover()

        # Titre
        self._title_var = ctk.StringVar(value="—")
        ctk.CTkLabel(np, textvariable=self._title_var, font=("Segoe UI", 15, "bold"),
                     text_color=TEXT, wraplength=240).grid(row=1, column=0, padx=16, sticky="ew")

        # Artiste
        self._artist_var = ctk.StringVar(value="—")
        ctk.CTkLabel(np, textvariable=self._artist_var, font=("Segoe UI", 12),
                     text_color=ACCLT).grid(row=2, column=0, padx=16, pady=(2, 10), sticky="ew")

        # Barre de progression
        prog_frame = ctk.CTkFrame(np, fg_color="transparent")
        prog_frame.grid(row=3, column=0, padx=16, pady=4, sticky="ew")
        prog_frame.grid_columnconfigure(0, weight=1)

        self._progress = ctk.CTkSlider(prog_frame, from_=0, to=1, number_of_steps=1000,
                                        fg_color=SURF3, progress_color=ACCENT,
                                        button_color=ACCLT, button_hover_color=ACCENT,
                                        height=14, corner_radius=4)
        self._progress.set(0)
        self._progress.grid(row=0, column=0, sticky="ew")
        self._progress.bind("<ButtonPress-1>",   self._seek_start)
        self._progress.bind("<ButtonRelease-1>", self._seek_end)

        times_frame = ctk.CTkFrame(np, fg_color="transparent")
        times_frame.grid(row=4, column=0, padx=16, sticky="ew")
        times_frame.grid_columnconfigure(1, weight=1)

        self._pos_var = ctk.StringVar(value="0:00")
        self._dur_var = ctk.StringVar(value="0:00")
        ctk.CTkLabel(times_frame, textvariable=self._pos_var,
                     text_color=MUTED, font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(times_frame, textvariable=self._dur_var,
                     text_color=MUTED, font=("Segoe UI", 10)).grid(row=0, column=2, sticky="e")

        # Boutons transport
        transport = ctk.CTkFrame(np, fg_color="transparent")
        transport.grid(row=5, column=0, padx=8, pady=8)

        btn_kw = dict(fg_color="transparent", hover_color=SURF3, text_color=TEXT,
                      width=44, height=44, corner_radius=22, font=("Segoe UI", 18))

        ctk.CTkButton(transport, text="⏮", command=self._prev, **btn_kw).grid(row=0, column=0)

        self._play_btn = ctk.CTkButton(transport, text="▶", command=self._toggle_play,
                                        fg_color=ACCENT, hover_color=ACCHOV, text_color=TEXT,
                                        width=52, height=52, corner_radius=26,
                                        font=("Segoe UI", 20))
        self._play_btn.grid(row=0, column=1, padx=4)

        ctk.CTkButton(transport, text="⏭", command=self._next, **btn_kw).grid(row=0, column=2)

        self._shuffle_btn = ctk.CTkButton(transport, text="🔀",
                                           command=self._toggle_shuffle,
                                           fg_color="transparent",
                                           hover_color=SURF3,
                                           text_color=MUTED if not self.cfg.shuffle else ACCENT,
                                           width=44, height=44, corner_radius=22,
                                           font=("Segoe UI", 16))
        self._shuffle_btn.grid(row=0, column=3, padx=(8, 0))

        self._repeat_btn = ctk.CTkButton(transport, text=self._repeat_icon(),
                                          command=self._cycle_repeat,
                                          fg_color="transparent",
                                          hover_color=SURF3,
                                          text_color=MUTED if self.cfg.repeat == "off" else ACCENT,
                                          width=44, height=44, corner_radius=22,
                                          font=("Segoe UI", 16))
        self._repeat_btn.grid(row=0, column=4)

        # Volume
        vol_frame = ctk.CTkFrame(np, fg_color="transparent")
        vol_frame.grid(row=6, column=0, padx=16, pady=(0, 8), sticky="ew")
        vol_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(vol_frame, text="🔊", text_color=MUTED,
                     font=("Segoe UI", 14)).grid(row=0, column=0, padx=(0, 6))

        self._vol_slider = ctk.CTkSlider(vol_frame, from_=0, to=1, number_of_steps=100,
                                          fg_color=SURF3, progress_color=SURF3,
                                          button_color=ACCLT, button_hover_color=ACCENT,
                                          height=14, corner_radius=4,
                                          command=self._on_volume_change)
        self._vol_slider.set(self.cfg.volume)
        self._vol_slider.grid(row=0, column=1, sticky="ew")

        # Port
        self._port_np_label = ctk.CTkLabel(np, text=f"Port : {self.cfg.overlay_port}",
                                            text_color=MUTED, font=("Segoe UI", 10))
        self._port_np_label.grid(row=7, column=0, padx=16, pady=(4, 16))

    # ══════════════════════════════════════════════════════════════════════════
    #  FOLDERS & FILES
    # ══════════════════════════════════════════════════════════════════════════

    def _add_folder(self) -> None:
        path = filedialog.askdirectory(title="Choisir un dossier audio")
        if not path:
            return
        if path not in self.cfg.folders:
            self.cfg.folders.append(path)
        files = scan_folder(path)
        new_files = [f for f in files if f not in self._queue]
        self._queue.extend(new_files)
        self._refresh_folder_list()
        self._refresh_queue_list()

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Choisir des fichiers audio",
            filetypes=[("Fichiers audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aiff *.aac"),
                       ("Tous les fichiers", "*.*")]
        )
        new_files = [p for p in paths if p not in self._queue]
        self._queue.extend(new_files)
        self._refresh_queue_list()

    def _load_folder(self, path: str) -> None:
        files = scan_folder(path)
        new_files = [f for f in files if f not in self._queue]
        self._queue.extend(new_files)
        self._refresh_queue_list()

    def _load_files(self, paths: list[str]) -> None:
        new_files = [p for p in paths if p not in self._queue]
        self._queue.extend(new_files)
        self._refresh_queue_list()

    def _remove_folder(self, path: str) -> None:
        if path in self.cfg.folders:
            self.cfg.folders.remove(path)
        self._refresh_folder_list()

    def _clear_queue(self) -> None:
        self.engine.stop()
        self._queue.clear()
        self._index = 0
        self._refresh_queue_list()
        write_stopped()

    # ══════════════════════════════════════════════════════════════════════════
    #  PLAYBACK
    # ══════════════════════════════════════════════════════════════════════════

    def _play_index(self, i: int) -> None:
        if not self._queue:
            return
        i = max(0, min(i, len(self._queue) - 1))
        self._index = i
        path = self._queue[i]
        try:
            self.engine.load(path)
            self.engine.play()
        except Exception:
            return

        self._track_id += 1
        title, artist, album, duration = self._cached_meta(path)
        if duration > 0 and self.engine.length == 0:
            self.engine._length = duration
        cover = find_cover(path)

        self._title_var.set(title)
        self._artist_var.set(artist or "—")
        self._play_btn.configure(text="⏸")
        self._update_cover(cover)
        self._refresh_queue_list()

        try:
            write_now_playing(
                title=title, artist=artist, album=album,
                duration=self.engine.length,
                position=0.0, playing=True,
                cover_src=cover,
                shuffle=self.cfg.shuffle,
                repeat=self.cfg.repeat,
                track_id=self._track_id,
            )
        except Exception:
            pass

    def _toggle_play(self) -> None:
        if not self._queue:
            return
        if self.engine.is_playing:
            self.engine.pause()
            self._play_btn.configure(text="▶")
        elif self.engine.is_paused:
            self.engine.resume()
            self._play_btn.configure(text="⏸")
        else:
            self._play_index(self._index)

    def _next(self) -> None:
        if not self._queue:
            return
        if self.cfg.shuffle:
            self._play_index(self._shuffled_next())
        elif self._index < len(self._queue) - 1:
            self._play_index(self._index + 1)
        elif self.cfg.repeat == "all":
            self._play_index(0)

    def _prev(self) -> None:
        if not self._queue:
            return
        pos = self.engine.position
        if pos > 3.0:
            self.engine.seek(0.0)
            return
        if self.cfg.shuffle:
            self._play_index(self._shuffled_prev())
        elif self._index > 0:
            self._play_index(self._index - 1)
        else:
            self.engine.seek(0.0)

    def _on_track_end(self) -> None:
        """Callback appelé par le thread du moteur — schedule dans le thread Tk."""
        self.after(50, self._handle_track_end)

    def _handle_track_end(self) -> None:
        if self.cfg.repeat == "one":
            self.engine.play(from_pos=0.0)
        else:
            self._next()

    def _shuffled_next(self) -> int:
        if not self._shuffle_order:
            self._shuffle_order = list(range(len(self._queue)))
            random.shuffle(self._shuffle_order)
        try:
            idx = self._shuffle_order.index(self._index)
            return self._shuffle_order[(idx + 1) % len(self._shuffle_order)]
        except ValueError:
            return self._shuffle_order[0]

    def _shuffled_prev(self) -> int:
        if not self._shuffle_order:
            self._shuffle_order = list(range(len(self._queue)))
            random.shuffle(self._shuffle_order)
        try:
            idx = self._shuffle_order.index(self._index)
            return self._shuffle_order[(idx - 1) % len(self._shuffle_order)]
        except ValueError:
            return self._shuffle_order[0]

    # ── Seek ──────────────────────────────────────────────────────────────────

    def _seek_start(self, _event) -> None:
        self._seeking = True

    def _seek_end(self, _event) -> None:
        self._seeking = False
        val = self._progress.get()
        seconds = val * self.engine.length
        self.engine.seek(seconds)

    # ── Volume ────────────────────────────────────────────────────────────────

    def _on_volume_change(self, val: float) -> None:
        self.engine.set_volume(val)
        self.cfg.volume = val

    # ── Shuffle / Repeat ─────────────────────────────────────────────────────

    def _toggle_shuffle(self) -> None:
        self.cfg.shuffle = not self.cfg.shuffle
        self._shuffle_order = []
        color = ACCENT if self.cfg.shuffle else MUTED
        self._shuffle_btn.configure(text_color=color)

    def _cycle_repeat(self) -> None:
        modes = ["off", "all", "one"]
        idx = modes.index(self.cfg.repeat)
        self.cfg.repeat = modes[(idx + 1) % len(modes)]
        self._repeat_btn.configure(
            text=self._repeat_icon(),
            text_color=MUTED if self.cfg.repeat == "off" else ACCENT
        )

    def _repeat_icon(self) -> str:
        return {"off": "🔁", "all": "🔁", "one": "🔂"}.get(self.cfg.repeat, "🔁")

    # ══════════════════════════════════════════════════════════════════════════
    #  TICK — 500 ms
    # ══════════════════════════════════════════════════════════════════════════

    def _tick(self) -> None:
        try:
            self._update_progress()
            self._write_state()
        except Exception:
            pass
        self.after(500, self._tick)

    def _update_progress(self) -> None:
        if self._seeking:
            return
        length = self.engine.length
        pos    = self.engine.position
        if length > 0:
            self._progress.set(pos / length)
        else:
            self._progress.set(0)
        self._pos_var.set(_fmt_time(pos))
        self._dur_var.set(_fmt_time(length))

        if self.engine.is_playing:
            self._play_btn.configure(text="⏸")
        elif self.engine.is_paused:
            self._play_btn.configure(text="▶")
        else:
            self._play_btn.configure(text="▶")

    def _write_state(self) -> None:
        if not self._queue or self._index >= len(self._queue):
            return
        path = self._queue[self._index]
        title, artist, album, _ = self._cached_meta(path)
        cover = find_cover(path)
        if self.engine.is_playing or self.engine.is_paused:
            try:
                write_now_playing(
                    title=title, artist=artist, album=album,
                    duration=self.engine.length,
                    position=self.engine.position,
                    playing=self.engine.is_playing,
                    cover_src=cover,
                    shuffle=self.cfg.shuffle,
                    repeat=self.cfg.repeat,
                    track_id=self._track_id,
                )
            except Exception:
                pass

    # ══════════════════════════════════════════════════════════════════════════
    #  REFRESH WIDGETS
    # ══════════════════════════════════════════════════════════════════════════

    def _refresh_queue_list(self) -> None:
        for w in self._queue_list.winfo_children():
            w.destroy()

        for i, path in enumerate(self._queue):
            title, artist, _, _ = self._cached_meta(path)
            label_text = f"{'▶ ' if i == self._index else '    '}{title}"
            if artist:
                label_text += f"  —  {artist}"

            bg = ACCENT if i == self._index else SURF3
            fg = TEXT

            row_btn = ctk.CTkButton(
                self._queue_list,
                text=label_text,
                fg_color=bg,
                hover_color=ACCHOV if i == self._index else SURF,
                text_color=fg,
                anchor="w",
                height=32,
                corner_radius=6,
                font=("Segoe UI", 11),
                command=lambda idx=i: self._play_index(idx),
            )
            row_btn.grid(row=i, column=0, padx=4, pady=1, sticky="ew")
            row_btn.bind("<Double-Button-1>", lambda e, idx=i: self._play_index(idx))

    def _refresh_folder_list(self) -> None:
        for w in self._folder_frame.winfo_children():
            w.destroy()

        for i, folder in enumerate(self.cfg.folders):
            row = ctk.CTkFrame(self._folder_frame, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew", pady=1)
            row.grid_columnconfigure(0, weight=1)

            name = Path(folder).name or folder
            artist_override = self.cfg.folder_artists.get(folder, "")
            display = f"📂 {name}"
            color = TEXT

            ctk.CTkLabel(row, text=display, text_color=color,
                         font=("Segoe UI", 11), anchor="w").grid(row=0, column=0, sticky="w")

            if artist_override:
                ctk.CTkLabel(row, text=artist_override, text_color=ACCLT,
                             font=("Segoe UI", 9), anchor="w").grid(row=1, column=0, sticky="w",
                                                                     columnspan=3, pady=(0, 2))

            ctk.CTkButton(row, text="✎", width=24, height=24, corner_radius=4,
                          fg_color="transparent", hover_color=SURF3, text_color=MUTED,
                          font=("Segoe UI", 10),
                          command=lambda p=folder: self._set_folder_artist(p)).grid(row=0, column=1)

            ctk.CTkButton(row, text="✕", width=24, height=24, corner_radius=4,
                          fg_color="transparent", hover_color=DANGER, text_color=MUTED,
                          font=("Segoe UI", 10),
                          command=lambda p=folder: self._remove_folder(p)).grid(row=0, column=2)

    def _set_folder_artist(self, folder: str) -> None:
        """Ouvre une fenêtre pour définir l'artiste par défaut d'un dossier."""
        current = self.cfg.folder_artists.get(folder, "")
        dialog = ctk.CTkInputDialog(
            text=f"Artiste pour :\n{Path(folder).name}\n\n(laisser vide pour supprimer)",
            title="Artiste du dossier",
        )
        value = dialog.get_input()
        if value is None:
            return
        value = value.strip()
        if value:
            self.cfg.folder_artists[folder] = value
        else:
            self.cfg.folder_artists.pop(folder, None)
        self._meta_cache.clear()
        self.cfg.save()
        self._refresh_folder_list()
        self._refresh_queue_list()
        # Mise à jour immédiate du panneau Now Playing si un titre est en cours
        if self._queue and self._index < len(self._queue):
            _, artist, _, _ = self._cached_meta(self._queue[self._index])
            self._artist_var.set(artist or "—")

    # ══════════════════════════════════════════════════════════════════════════
    #  COVER
    # ══════════════════════════════════════════════════════════════════════════

    def _update_cover(self, cover_path: str | None) -> None:
        try:
            if cover_path and Path(cover_path).exists():
                img = Image.open(cover_path).convert("RGB")
                img = img.resize((200, 200), Image.LANCZOS)
            else:
                img = _make_placeholder(200)
            self._cover_img = ImageTk.PhotoImage(img)
            self._cover_label.configure(image=self._cover_img, text="")
        except Exception:
            self._set_placeholder_cover()

    def _set_placeholder_cover(self) -> None:
        try:
            img = _make_placeholder(200)
            self._cover_img = ImageTk.PhotoImage(img)
            self._cover_label.configure(image=self._cover_img, text="")
        except Exception:
            self._cover_label.configure(image=None, text="♫")

    # ══════════════════════════════════════════════════════════════════════════
    #  OBS / MISC
    # ══════════════════════════════════════════════════════════════════════════

    def _copy_obs_url(self) -> None:
        url = f"http://localhost:{self.cfg.overlay_port}/overlay/index.html"
        self.clipboard_clear()
        self.clipboard_append(url)

    # ══════════════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ══════════════════════════════════════════════════════════════════════════

    def _on_close(self) -> None:
        try:
            self.cfg.queue       = list(self._queue)
            self.cfg.queue_index = self._index
            self.cfg.volume      = self.engine.volume
            self.cfg.window_geometry = self.geometry()
            self.cfg.save()
        except Exception:
            pass
        try:
            write_stopped()
        except Exception:
            pass
        try:
            self.engine.stop()
        except Exception:
            pass
        try:
            self.server.shutdown()
        except Exception:
            pass
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _fmt_time(sec: float) -> str:
    s = int(max(0, sec))
    return f"{s // 60}:{s % 60:02d}"


def _make_placeholder(size: int) -> "Image.Image":
    img = Image.new("RGB", (size, size), "#1a1a1a")
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.text((size // 2, size // 2), "♫", fill="#444444", anchor="mm")
    return img
