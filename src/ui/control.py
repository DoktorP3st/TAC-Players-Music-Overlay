"""Interface de contrôle — customtkinter."""
from __future__ import annotations

import random
import tkinter as tk
from pathlib import Path
from tkinter import filedialog
from tkinter.colorchooser import askcolor

import customtkinter as ctk
from PIL import Image, ImageTk

from src.core.config import AppConfig, data_dir
from src.core.scanner import scan_folder, find_cover
from src.player.engine import AudioEngine
from src.player.writer import write_now_playing, write_stopped

# ── Palette ───────────────────────────────────────────────────────────────────
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

# ── Thèmes prédéfinis ─────────────────────────────────────────────────────────
OV_THEMES: dict[str, dict] = {
    "glassmorphism": dict(
        ov_opacity=0.82, ov_blur=20, ov_bg="#0a0a0a", ov_radius=16, ov_width=420,
        ov_accent="#7c3aed", ov_title_color="#f4f4f5", ov_artist_color="#a78bfa",
        ov_title_size=15, ov_artist_size=12, ov_transition=0.30,
    ),
    "dark_minimal": dict(
        ov_opacity=0.96, ov_blur=0,  ov_bg="#0d0d0d", ov_radius=8,  ov_width=420,
        ov_accent="#ffffff", ov_title_color="#ffffff", ov_artist_color="#888888",
        ov_title_size=14, ov_artist_size=12, ov_transition=0.20,
    ),
    "neon": dict(
        ov_opacity=0.92, ov_blur=5,  ov_bg="#020202", ov_radius=4,  ov_width=420,
        ov_accent="#00ff88", ov_title_color="#00ff88", ov_artist_color="#00ccaa",
        ov_title_size=14, ov_artist_size=11, ov_transition=0.15,
    ),
    "sakura": dict(
        ov_opacity=0.86, ov_blur=15, ov_bg="#1a0a1f", ov_radius=22, ov_width=420,
        ov_accent="#e879f9", ov_title_color="#fce7f3", ov_artist_color="#f0abfc",
        ov_title_size=15, ov_artist_size=12, ov_transition=0.50,
    ),
}

_THEME_LABELS = {
    "glassmorphism": "Glassmorphism",
    "dark_minimal":  "Dark Minimal",
    "neon":          "Neon",
    "sakura":        "Sakura",
}

# Canvas preview
_PV_W  = 440
_PV_H  = 118
_PV_BG = "#181818"


# ══════════════════════════════════════════════════════════════════════════════

def _read_meta(path: str) -> tuple[str, str, str]:
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


# ══════════════════════════════════════════════════════════════════════════════
class ControlPanel(ctk.CTk):
    def __init__(self, cfg: AppConfig, server) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        self.cfg    = cfg
        self.server = server
        self.engine = AudioEngine()
        self.engine.on_end(self._on_track_end)

        self._queue: list[str]         = list(cfg.queue)
        self._index: int               = cfg.queue_index
        self._shuffle_order: list[int] = []
        self._seeking: bool            = False
        self._cover_img:  ImageTk.PhotoImage | None = None
        self._meta_cache: dict[str, tuple[str, str, str, float]] = {}
        self._track_id: int = 0

        # Preview
        self._preview_cover_photo: ImageTk.PhotoImage | None = None
        self._preview_track_id: int = -1

        # Visual settings widget refs
        self._vis_sliders:     dict[str, ctk.CTkSlider]    = {}
        self._vis_val_vars:    dict[str, ctk.StringVar]    = {}
        self._vis_swatches:    dict[str, ctk.CTkFrame]     = {}
        self._vis_hex_vars:    dict[str, ctk.StringVar]    = {}
        self._vis_display_fns: dict[str, object]           = {}
        self._vis_theme_btns:  dict[str, ctk.CTkButton]   = {}
        self._vis_checkboxes:  dict[str, ctk.CTkCheckBox] = {}
        self._vis_bool_vars:   dict[str, ctk.BooleanVar]  = {}

        self.title("Music Player Overlay")
        self.geometry(cfg.window_geometry)
        self.configure(fg_color=BG)
        self.resizable(True, True)
        self.minsize(1020, 640)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._refresh_queue_list()
        self._refresh_folder_list()
        self._tick()

    # ──────────────────────────────────────────────────────────────────────────
    #  META HELPERS
    # ──────────────────────────────────────────────────────────────────────────

    def _get_folder_artist(self, path: str) -> str:
        folder = Path(path).parent.resolve()
        for registered, artist in self.cfg.folder_artists.items():
            try:
                folder.relative_to(Path(registered).resolve())
                return artist
            except ValueError:
                pass
        return ""

    def _force_refresh(self) -> None:
        self._meta_cache.clear()
        self._write_state()
        self._refresh_btn.configure(text="✓ OK", text_color=SUCCESS)
        self.after(1200, lambda: self._refresh_btn.configure(
            text="Rafraîchir", text_color=MUTED))

    def _cached_meta(self, path: str) -> tuple[str, str, str, float]:
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
        self.grid_columnconfigure(0, weight=0, minsize=240)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=300)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_center_panel()
        self._build_now_playing()

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def _build_sidebar(self) -> None:
        sb = ctk.CTkFrame(self, fg_color=SURF, corner_radius=0,
                          border_width=0)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_columnconfigure(0, weight=1)
        sb.grid_rowconfigure(2, weight=1)

        # ── Branding ──────────────────────────────────────────────────────────
        brand = ctk.CTkFrame(sb, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=14, pady=(16, 12))
        ctk.CTkLabel(brand, text="♫", font=("Segoe UI", 22),
                     text_color=ACCENT).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(brand, text="Music Overlay", font=("Segoe UI", 13, "bold"),
                     text_color=TEXT).pack(side="left")

        _hsep(sb, row=1)

        # ── Dossiers ──────────────────────────────────────────────────────────
        folders_block = ctk.CTkFrame(sb, fg_color="transparent")
        folders_block.grid(row=2, column=0, sticky="nsew")
        folders_block.grid_columnconfigure(0, weight=1)
        folders_block.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(folders_block, text="DOSSIERS",
                     font=("Segoe UI", 9, "bold"), text_color=MUTED).grid(
            row=0, column=0, padx=14, pady=(12, 6), sticky="w")

        self._folder_frame = ctk.CTkScrollableFrame(
            folders_block, fg_color=SURF2, corner_radius=8, height=180,
            scrollbar_button_color=SURF3, scrollbar_button_hover_color=ACCENT)
        self._folder_frame.grid(row=1, column=0, padx=8, pady=(0, 8), sticky="nsew")
        self._folder_frame.grid_columnconfigure(0, weight=1)

        add_row = ctk.CTkFrame(folders_block, fg_color="transparent")
        add_row.grid(row=2, column=0, padx=8, pady=(0, 4), sticky="ew")
        add_row.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(add_row, text="+ Dossier", fg_color=SURF3, hover_color=ACCENT,
                      text_color=TEXT, height=30, corner_radius=8,
                      font=("Segoe UI", 11),
                      command=self._add_folder).grid(row=0, column=0, padx=(0, 3), sticky="ew")
        ctk.CTkButton(add_row, text="+ Fichiers", fg_color=SURF3, hover_color=ACCENT,
                      text_color=TEXT, height=30, corner_radius=8,
                      font=("Segoe UI", 11),
                      command=self._add_files).grid(row=0, column=1, padx=(3, 0), sticky="ew")

        _hsep(sb, row=3)

        # ── Overlay OBS ───────────────────────────────────────────────────────
        obs_block = ctk.CTkFrame(sb, fg_color="transparent")
        obs_block.grid(row=4, column=0, sticky="ew", padx=14, pady=(10, 4))
        obs_block.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(obs_block, text="OBS OVERLAY",
                     font=("Segoe UI", 9, "bold"), text_color=MUTED).grid(
            row=0, column=0, sticky="w", pady=(0, 6))

        status_row = ctk.CTkFrame(obs_block, fg_color="transparent")
        status_row.grid(row=1, column=0, sticky="ew")
        ctk.CTkLabel(status_row, text="●", font=("Segoe UI", 11),
                     text_color=SUCCESS).pack(side="left", padx=(0, 5))
        ctk.CTkLabel(status_row, text="Actif",
                     font=("Segoe UI", 11), text_color=TEXT).pack(side="left")
        ctk.CTkLabel(status_row,
                     text=f"Port {self.cfg.overlay_port}",
                     font=("Segoe UI", 10), text_color=MUTED).pack(side="right")

        obs_btns = ctk.CTkFrame(obs_block, fg_color="transparent")
        obs_btns.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        obs_btns.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(obs_btns, text="Copier URL", fg_color=SURF3, hover_color=ACCENT,
                      text_color=TEXT, height=30, corner_radius=8,
                      font=("Segoe UI", 11),
                      command=self._copy_obs_url).grid(row=0, column=0, padx=(0, 3), sticky="ew")

        self._refresh_btn = ctk.CTkButton(
            obs_btns, text="Rafraîchir", fg_color=SURF3,
            hover_color=SURF3, text_color=MUTED, height=30, corner_radius=8,
            font=("Segoe UI", 11), command=self._force_refresh)
        self._refresh_btn.grid(row=0, column=1, padx=(3, 0), sticky="ew")

        _hsep(sb, row=5, pady=(10, 14))

    # ── Panneau central avec navigation custom ────────────────────────────────

    def _build_center_panel(self) -> None:
        outer = ctk.CTkFrame(self, fg_color=SURF2, corner_radius=0,
                             border_width=1, border_color=BORDER)
        outer.grid(row=0, column=1, sticky="nsew")
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)

        # ── Barre de navigation ───────────────────────────────────────────────
        nav = ctk.CTkFrame(outer, fg_color=SURF, corner_radius=0, height=46)
        nav.grid(row=0, column=0, sticky="ew")
        nav.grid_propagate(False)
        nav.grid_columnconfigure((0, 1), weight=1)
        nav.grid_rowconfigure(0, weight=1)

        self._nav_queue_btn = ctk.CTkButton(
            nav, text="FILE D'ATTENTE",
            fg_color="transparent", hover_color=SURF2,
            text_color=TEXT, font=("Segoe UI", 11, "bold"),
            corner_radius=0, border_width=0, height=46,
            command=lambda: self._show_center("queue"),
        )
        self._nav_queue_btn.grid(row=0, column=0, sticky="nsew")

        self._nav_overlay_btn = ctk.CTkButton(
            nav, text="OVERLAY VISUEL",
            fg_color="transparent", hover_color=SURF2,
            text_color=MUTED, font=("Segoe UI", 11),
            corner_radius=0, border_width=0, height=46,
            command=lambda: self._show_center("overlay"),
        )
        self._nav_overlay_btn.grid(row=0, column=1, sticky="nsew")

        # Indicateur accent coulissant — height dans le constructeur (CTK exige ça)
        self._nav_indicator = ctk.CTkFrame(nav, fg_color=ACCENT,
                                            height=3, corner_radius=0)
        self._nav_indicator.place(relx=0.0, rely=1.0,
                                   relwidth=0.5, anchor="sw")

        # Séparateur fin
        ctk.CTkFrame(outer, fg_color=BORDER, height=1,
                     corner_radius=0).grid(row=0, column=0, sticky="sew")

        # ── Zone de contenu (panes empilées) ──────────────────────────────────
        content = ctk.CTkFrame(outer, fg_color="transparent", corner_radius=0)
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self._queue_pane = ctk.CTkFrame(content, fg_color=SURF2, corner_radius=0)
        self._queue_pane.grid(row=0, column=0, sticky="nsew")

        self._overlay_pane = ctk.CTkFrame(content, fg_color=BG, corner_radius=0)
        self._overlay_pane.grid(row=0, column=0, sticky="nsew")

        self._build_queue_content(self._queue_pane)
        self._build_overlay_content(self._overlay_pane)

        # Queue visible par défaut
        self._queue_pane.tkraise()

    def _show_center(self, which: str) -> None:
        """Bascule entre la file d'attente et les réglages overlay."""
        is_q = (which == "queue")
        self._nav_queue_btn.configure(
            text_color=TEXT if is_q else MUTED,
            font=("Segoe UI", 11, "bold") if is_q else ("Segoe UI", 11),
        )
        self._nav_overlay_btn.configure(
            text_color=TEXT if not is_q else MUTED,
            font=("Segoe UI", 11, "bold") if not is_q else ("Segoe UI", 11),
        )
        self._nav_indicator.place(
            relx=0.0 if is_q else 0.5,
            rely=1.0, relwidth=0.5, anchor="sw",
        )
        (self._queue_pane if is_q else self._overlay_pane).tkraise()

    # ── File d'attente ────────────────────────────────────────────────────────

    def _build_queue_content(self, parent: ctk.CTkFrame) -> None:
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.grid(row=0, column=0, padx=14, pady=(14, 6), sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="FILE D'ATTENTE",
                     font=("Segoe UI", 9, "bold"), text_color=MUTED).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="Vider", fg_color=SURF3, hover_color=DANGER,
                      text_color=MUTED, height=24, width=58, corner_radius=6,
                      font=("Segoe UI", 10),
                      command=self._clear_queue).grid(row=0, column=1)

        self._queue_list = ctk.CTkScrollableFrame(
            parent, fg_color="transparent",
            scrollbar_button_color=SURF3, scrollbar_button_hover_color=ACCENT)
        self._queue_list.grid(row=1, column=0, padx=4, pady=(0, 4), sticky="nsew")
        self._queue_list.grid_columnconfigure(0, weight=1)

    # ── Overlay — preview + réglages ─────────────────────────────────────────

    def _build_overlay_content(self, parent: ctk.CTkFrame) -> None:
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        # ── Carte preview ─────────────────────────────────────────────────────
        card = ctk.CTkFrame(parent, fg_color=SURF, corner_radius=12,
                             border_width=1, border_color=BORDER)
        card.grid(row=0, column=0, padx=16, pady=(16, 8), sticky="ew")
        card.grid_columnconfigure(0, weight=1)

        # En-tête carte
        card_hdr = ctk.CTkFrame(card, fg_color="transparent")
        card_hdr.grid(row=0, column=0, padx=14, pady=(12, 8), sticky="ew")
        card_hdr.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(card_hdr, text="PRÉVISUALISATION",
                     font=("Segoe UI", 9, "bold"), text_color=MUTED).grid(
            row=0, column=0, sticky="w")
        self._live_badge = ctk.CTkLabel(card_hdr, text="● LIVE",
                                         font=("Segoe UI", 9, "bold"),
                                         text_color=SUCCESS)
        self._live_badge.grid(row=0, column=1, sticky="e")

        # Canvas preview
        canvas_bg = ctk.CTkFrame(card, fg_color=_PV_BG, corner_radius=8)
        canvas_bg.grid(row=1, column=0, padx=14, pady=(0, 10), sticky="ew")
        self._preview_canvas = tk.Canvas(
            canvas_bg, bg=_PV_BG, highlightthickness=0,
            width=_PV_W, height=_PV_H)
        self._preview_canvas.pack(pady=10)

        # Thèmes prédéfinis
        themes_row = ctk.CTkFrame(card, fg_color="transparent")
        themes_row.grid(row=2, column=0, padx=14, pady=(0, 14), sticky="ew")
        ctk.CTkLabel(themes_row, text="THÈME",
                     font=("Segoe UI", 9, "bold"), text_color=MUTED).pack(
            side="left", padx=(0, 10))
        for key, label in _THEME_LABELS.items():
            active = (self.cfg.ov_theme == key)
            btn = ctk.CTkButton(
                themes_row, text=label,
                fg_color=ACCENT if active else SURF3,
                hover_color=ACCHOV, text_color=TEXT,
                height=28, corner_radius=6, font=("Segoe UI", 11),
                command=lambda k=key: self._apply_theme_preset(k),
            )
            btn.pack(side="left", padx=2)
            self._vis_theme_btns[key] = btn

        # ── Réglages scrollables ──────────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(
            parent, fg_color="transparent",
            scrollbar_button_color=SURF3, scrollbar_button_hover_color=ACCENT)
        scroll.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        scroll.grid_columnconfigure(0, weight=1)
        self._build_visual_settings_form(scroll)

        self._draw_preview()

    # ── Formulaire réglages visuels ───────────────────────────────────────────

    def _build_visual_settings_form(self, parent: ctk.CTkFrame) -> None:
        row = 0

        def section(text: str) -> None:
            nonlocal row
            ctk.CTkLabel(parent, text=text,
                         font=("Segoe UI", 9, "bold"), text_color=MUTED).grid(
                row=row, column=0, padx=16, pady=(16, 4), sticky="w")
            row += 1

        def sep() -> None:
            nonlocal row
            ctk.CTkFrame(parent, fg_color=BORDER, height=1).grid(
                row=row, column=0, padx=16, pady=(6, 0), sticky="ew")
            row += 1

        def slider(label: str, attr: str, lo: float, hi: float,
                   steps: int, dfn) -> None:
            nonlocal row
            self._vis_display_fns[attr] = dfn
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.grid(row=row, column=0, padx=16, pady=(2, 2), sticky="ew")
            f.grid_columnconfigure(1, weight=1)
            row += 1

            ctk.CTkLabel(f, text=label, text_color=TEXT,
                         font=("Segoe UI", 11), width=150,
                         anchor="w").grid(row=0, column=0, sticky="w")

            cur = getattr(self.cfg, attr)
            orig_type = type(cur)
            val_var = ctk.StringVar(value=dfn(cur))
            self._vis_val_vars[attr] = val_var

            def _cb(v, _a=attr, _var=val_var, _dfn=dfn, _t=orig_type):
                cast = _t(round(v) if _t is int else v)
                setattr(self.cfg, _a, cast)
                _var.set(_dfn(cast))
                self._vis_immediate()

            sl = ctk.CTkSlider(f, from_=lo, to=hi, number_of_steps=steps,
                               fg_color=SURF3, progress_color=ACCENT,
                               button_color=ACCLT, button_hover_color=ACCENT,
                               height=14, corner_radius=4, command=_cb)
            sl.set(cur)
            sl.grid(row=0, column=1, padx=(10, 8), sticky="ew")
            self._vis_sliders[attr] = sl

            ctk.CTkLabel(f, textvariable=val_var, text_color=ACCLT,
                         font=("Segoe UI", 10), width=58,
                         anchor="e").grid(row=0, column=2)

        def color_btn(label: str, attr: str) -> None:
            nonlocal row
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.grid(row=row, column=0, padx=16, pady=(2, 2), sticky="ew")
            f.grid_columnconfigure(2, weight=1)
            row += 1

            ctk.CTkLabel(f, text=label, text_color=TEXT,
                         font=("Segoe UI", 11), width=150,
                         anchor="w").grid(row=0, column=0, sticky="w")

            cur = getattr(self.cfg, attr)
            swatch = ctk.CTkFrame(f, width=22, height=22, corner_radius=4,
                                   fg_color=cur)
            swatch.grid(row=0, column=1, padx=(10, 6))
            self._vis_swatches[attr] = swatch

            hex_var = ctk.StringVar(value=cur)
            self._vis_hex_vars[attr] = hex_var
            ctk.CTkLabel(f, textvariable=hex_var, text_color=MUTED,
                         font=("Segoe UI Mono", 10)).grid(
                row=0, column=2, sticky="w")

            def _pick(_a=attr, _sw=swatch, _hv=hex_var):
                result = askcolor(color=getattr(self.cfg, _a),
                                  title=f"Couleur — {label}")
                if result and result[1]:
                    c = result[1]
                    setattr(self.cfg, _a, c)
                    _sw.configure(fg_color=c)
                    _hv.set(c)
                    self._vis_immediate()

            ctk.CTkButton(f, text="Choisir", fg_color=SURF3, hover_color=ACCENT,
                          text_color=TEXT, height=26, width=72, corner_radius=6,
                          font=("Segoe UI", 10),
                          command=_pick).grid(row=0, column=3, padx=(6, 0))

        def toggle(label: str, attr: str) -> None:
            nonlocal row
            bv = ctk.BooleanVar(value=getattr(self.cfg, attr))
            self._vis_bool_vars[attr] = bv

            def _cb(_a=attr, _bv=bv):
                setattr(self.cfg, _a, _bv.get())
                self._vis_immediate()

            cb = ctk.CTkCheckBox(parent, text=label, variable=bv, command=_cb,
                                 text_color=TEXT, font=("Segoe UI", 11),
                                 fg_color=ACCENT, hover_color=ACCHOV,
                                 checkmark_color=TEXT)
            cb.grid(row=row, column=0, padx=20, pady=(3, 3), sticky="w")
            self._vis_checkboxes[attr] = cb
            row += 1

        # ── APPARENCE ─────────────────────────────────────────────────────────
        section("APPARENCE")
        slider("Opacité du fond",  "ov_opacity", 0.05, 1.0, 95,
               lambda v: f"{int(round(v * 100))} %")
        slider("Flou (blur)",      "ov_blur",    0, 40, 40,
               lambda v: f"{int(round(v))} px")
        slider("Rayon des coins",  "ov_radius",  0, 40, 40,
               lambda v: f"{int(round(v))} px")
        slider("Largeur overlay",  "ov_width",   280, 700, 422,
               lambda v: f"{int(round(v))} px")
        sep()

        # ── COULEURS ──────────────────────────────────────────────────────────
        section("COULEURS")
        color_btn("Couleur du fond",  "ov_bg")
        color_btn("Couleur accent",   "ov_accent")
        color_btn("Couleur titre",    "ov_title_color")
        color_btn("Couleur artiste",  "ov_artist_color")
        sep()

        # ── TYPOGRAPHIE ───────────────────────────────────────────────────────
        section("TYPOGRAPHIE")
        slider("Taille titre",    "ov_title_size",   9, 26, 17,
               lambda v: f"{int(round(v))} px")
        slider("Taille artiste",  "ov_artist_size",  8, 22, 14,
               lambda v: f"{int(round(v))} px")
        sep()

        # ── ÉLÉMENTS ──────────────────────────────────────────────────────────
        section("ÉLÉMENTS VISIBLES")
        toggle("Afficher la pochette d'album",       "ov_show_cover")
        toggle("Afficher la barre de progression",   "ov_show_progress")
        sep()

        # ── ANIMATIONS ────────────────────────────────────────────────────────
        section("ANIMATIONS")
        slider("Vitesse de transition", "ov_transition", 0.05, 1.2, 23,
               lambda v: f"{v:.2f} s")
        sep()

        # ── Bouton sauvegarder ────────────────────────────────────────────────
        self._save_vis_btn = ctk.CTkButton(
            parent, text="Sauvegarder le profil visuel",
            fg_color=ACCENT, hover_color=ACCHOV,
            text_color=TEXT, height=38, corner_radius=8,
            font=("Segoe UI", 11, "bold"),
            command=self._save_visual_profile,
        )
        self._save_vis_btn.grid(row=row, column=0, padx=16, pady=(6, 16), sticky="ew")

    # ── Now Playing ───────────────────────────────────────────────────────────

    def _build_now_playing(self) -> None:
        np = ctk.CTkFrame(self, fg_color=SURF, corner_radius=0,
                          border_width=1, border_color=BORDER)
        np.grid(row=0, column=2, sticky="nsew")
        np.grid_columnconfigure(0, weight=1)
        np.grid_rowconfigure(8, weight=1)

        # Cover
        self._cover_label = ctk.CTkLabel(np, text="", width=200, height=200)
        self._cover_label.grid(row=0, column=0, padx=20, pady=(24, 10))
        self._set_placeholder_cover()

        # Titre + artiste
        self._title_var = ctk.StringVar(value="—")
        ctk.CTkLabel(np, textvariable=self._title_var,
                     font=("Segoe UI", 15, "bold"), text_color=TEXT,
                     wraplength=252).grid(row=1, column=0, padx=18, sticky="ew")

        self._artist_var = ctk.StringVar(value="—")
        ctk.CTkLabel(np, textvariable=self._artist_var,
                     font=("Segoe UI", 12), text_color=ACCLT).grid(
            row=2, column=0, padx=18, pady=(2, 12), sticky="ew")

        # Barre de progression
        prog_frame = ctk.CTkFrame(np, fg_color="transparent")
        prog_frame.grid(row=3, column=0, padx=18, pady=0, sticky="ew")
        prog_frame.grid_columnconfigure(0, weight=1)

        self._progress = ctk.CTkSlider(
            prog_frame, from_=0, to=1, number_of_steps=1000,
            fg_color=SURF3, progress_color=ACCENT,
            button_color=ACCLT, button_hover_color=ACCENT,
            height=14, corner_radius=4)
        self._progress.set(0)
        self._progress.grid(row=0, column=0, sticky="ew")
        self._progress.bind("<ButtonPress-1>",   self._seek_start)
        self._progress.bind("<ButtonRelease-1>", self._seek_end)

        times = ctk.CTkFrame(np, fg_color="transparent")
        times.grid(row=4, column=0, padx=18, pady=(2, 0), sticky="ew")
        times.grid_columnconfigure(1, weight=1)

        self._pos_var = ctk.StringVar(value="0:00")
        self._dur_var = ctk.StringVar(value="0:00")
        ctk.CTkLabel(times, textvariable=self._pos_var,
                     text_color=MUTED, font=("Segoe UI", 10)).grid(
            row=0, column=0, sticky="w")
        ctk.CTkLabel(times, textvariable=self._dur_var,
                     text_color=MUTED, font=("Segoe UI", 10)).grid(
            row=0, column=2, sticky="e")

        # Transport
        transport = ctk.CTkFrame(np, fg_color="transparent")
        transport.grid(row=5, column=0, pady=(12, 4))

        kw = dict(fg_color="transparent", hover_color=SURF3, text_color=TEXT,
                  width=44, height=44, corner_radius=22, font=("Segoe UI", 18))
        ctk.CTkButton(transport, text="⏮", command=self._prev, **kw).grid(row=0, column=0)

        self._play_btn = ctk.CTkButton(
            transport, text="▶", command=self._toggle_play,
            fg_color=ACCENT, hover_color=ACCHOV, text_color=TEXT,
            width=54, height=54, corner_radius=27, font=("Segoe UI", 20))
        self._play_btn.grid(row=0, column=1, padx=6)

        ctk.CTkButton(transport, text="⏭", command=self._next, **kw).grid(row=0, column=2)

        self._shuffle_btn = ctk.CTkButton(
            transport, text="🔀", command=self._toggle_shuffle,
            fg_color="transparent", hover_color=SURF3,
            text_color=MUTED if not self.cfg.shuffle else ACCENT,
            width=40, height=40, corner_radius=20, font=("Segoe UI", 15))
        self._shuffle_btn.grid(row=0, column=3, padx=(8, 0))

        self._repeat_btn = ctk.CTkButton(
            transport, text=self._repeat_icon(), command=self._cycle_repeat,
            fg_color="transparent", hover_color=SURF3,
            text_color=MUTED if self.cfg.repeat == "off" else ACCENT,
            width=40, height=40, corner_radius=20, font=("Segoe UI", 15))
        self._repeat_btn.grid(row=0, column=4)

        # Volume
        vol = ctk.CTkFrame(np, fg_color="transparent")
        vol.grid(row=6, column=0, padx=18, pady=(4, 0), sticky="ew")
        vol.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(vol, text="🔊", text_color=MUTED,
                     font=("Segoe UI", 13)).grid(row=0, column=0, padx=(0, 8))
        self._vol_slider = ctk.CTkSlider(
            vol, from_=0, to=1, number_of_steps=100,
            fg_color=SURF3, progress_color=SURF3,
            button_color=ACCLT, button_hover_color=ACCENT,
            height=14, corner_radius=4, command=self._on_volume_change)
        self._vol_slider.set(self.cfg.volume)
        self._vol_slider.grid(row=0, column=1, sticky="ew")

        # Spacer + port
        ctk.CTkFrame(np, fg_color="transparent").grid(row=8, column=0, sticky="nsew")
        ctk.CTkLabel(np, text=f"Port {self.cfg.overlay_port}",
                     text_color=MUTED, font=("Segoe UI", 9)).grid(
            row=9, column=0, pady=(0, 14))

    # ══════════════════════════════════════════════════════════════════════════
    #  THÈMES & RÉGLAGES VISUELS
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_theme_preset(self, name: str) -> None:
        for attr, val in OV_THEMES.get(name, {}).items():
            setattr(self.cfg, attr, val)
        self.cfg.ov_theme = name
        self._refresh_vis_widgets()
        self._vis_immediate()
        for k, btn in self._vis_theme_btns.items():
            btn.configure(fg_color=ACCENT if k == name else SURF3)

    def _refresh_vis_widgets(self) -> None:
        for attr, sl in self._vis_sliders.items():
            sl.set(getattr(self.cfg, attr))
        for attr, var in self._vis_val_vars.items():
            dfn = self._vis_display_fns.get(attr, str)
            var.set(dfn(getattr(self.cfg, attr)))
        for attr, sw in self._vis_swatches.items():
            sw.configure(fg_color=getattr(self.cfg, attr))
        for attr, var in self._vis_hex_vars.items():
            var.set(getattr(self.cfg, attr))
        for attr, bv in self._vis_bool_vars.items():
            bv.set(getattr(self.cfg, attr))

    def _vis_immediate(self) -> None:
        self._draw_preview()
        self._write_state()

    def _save_visual_profile(self) -> None:
        self.cfg.save()
        self._save_vis_btn.configure(text="✓  Profil sauvegardé !", text_color=SUCCESS)
        self.after(2000, lambda: self._save_vis_btn.configure(
            text="Sauvegarder le profil visuel", text_color=TEXT))

    # ══════════════════════════════════════════════════════════════════════════
    #  PREVIEW CANVAS
    # ══════════════════════════════════════════════════════════════════════════

    def _update_preview(self) -> None:
        if not hasattr(self, "_preview_canvas"):
            return
        if self._track_id != self._preview_track_id:
            self._preview_track_id = self._track_id
            self._load_preview_cover()
        self._draw_preview()

    def _load_preview_cover(self) -> None:
        cover_path = data_dir() / "cover.jpg"
        try:
            if cover_path.exists():
                img = Image.open(cover_path).convert("RGB")
                img = img.resize((68, 68), Image.LANCZOS)
                self._preview_cover_photo = ImageTk.PhotoImage(img)
                return
        except Exception:
            pass
        try:
            self._preview_cover_photo = ImageTk.PhotoImage(_make_placeholder(68))
        except Exception:
            self._preview_cover_photo = None

    def _draw_preview(self) -> None:
        if not hasattr(self, "_preview_canvas"):
            return
        c   = self._preview_canvas
        cfg = self.cfg
        c.delete("all")

        ov_w   = min(cfg.ov_width, _PV_W - 20)
        ov_h   = 98
        x0     = (_PV_W - ov_w) // 2
        y0     = (_PV_H - ov_h) // 2
        x1, y1 = x0 + ov_w, y0 + ov_h

        blend  = _blend_hex(cfg.ov_bg, _PV_BG, cfg.ov_opacity)
        border = _blend_hex("#ffffff", blend, 0.18)
        _draw_rrect(c, x0, y0, x1, y1, cfg.ov_radius, fill=blend, outline=border)

        pad = 14
        if cfg.ov_show_cover:
            cx, cy = x0 + pad, y0 + (ov_h - 68) // 2
            if self._preview_cover_photo:
                c.create_image(cx, cy, image=self._preview_cover_photo, anchor="nw")
            else:
                c.create_rectangle(cx, cy, cx + 68, cy + 68,
                                    fill="#2a2a2a", outline="")
                c.create_text(cx + 34, cy + 34, text="♫",
                               fill="#444", font=("Segoe UI", 18))
            info_x = x0 + pad + 68 + pad
        else:
            info_x = x0 + pad

        info_w = x1 - info_x - pad
        mid_y  = y0 + ov_h // 2

        title = (getattr(self, "_title_var", None) or ctk.StringVar(value="")).get()
        if not title or title == "—":
            title = "Titre de la piste"
        c.create_text(
            info_x, mid_y - 22,
            text=_trunc(title, info_w, cfg.ov_title_size),
            fill=cfg.ov_title_color,
            font=("Segoe UI", max(9, min(cfg.ov_title_size, 18)), "bold"),
            anchor="w",
        )

        artist = (getattr(self, "_artist_var", None) or ctk.StringVar(value="")).get()
        if not artist or artist == "—":
            artist = "Artiste"
        c.create_text(
            info_x, mid_y - 6,
            text=_trunc(artist, info_w, cfg.ov_artist_size),
            fill=cfg.ov_artist_color,
            font=("Segoe UI", max(8, min(cfg.ov_artist_size, 16))),
            anchor="w",
        )

        if cfg.ov_show_progress:
            pb_y  = mid_y + 14
            pb_x0, pb_x1 = info_x, x1 - pad
            pb_w  = max(1, pb_x1 - pb_x0)

            c.create_rectangle(pb_x0, pb_y, pb_x1, pb_y + 3,
                                fill="#404040", outline="")

            prog = 0.0
            if self.engine.length > 0:
                prog = min(1.0, self.engine.position / self.engine.length)
            fw = int(pb_w * prog)
            if fw > 0:
                c.create_rectangle(pb_x0, pb_y, pb_x0 + fw, pb_y + 3,
                                    fill=cfg.ov_accent, outline="")

            c.create_text(pb_x0, pb_y + 9, text=_fmt_time(self.engine.position),
                           fill="#71717a", font=("Segoe UI", 8), anchor="w")
            c.create_text(pb_x1,  pb_y + 9, text=_fmt_time(self.engine.length),
                           fill="#71717a", font=("Segoe UI", 8), anchor="e")

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
        self._queue.extend(f for f in files if f not in self._queue)
        self._refresh_folder_list()
        self._refresh_queue_list()

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Choisir des fichiers audio",
            filetypes=[("Fichiers audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aiff *.aac"),
                       ("Tous les fichiers", "*.*")])
        self._queue.extend(p for p in paths if p not in self._queue)
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
                duration=self.engine.length, position=0.0,
                playing=True, cover_src=cover,
                shuffle=self.cfg.shuffle, repeat=self.cfg.repeat,
                track_id=self._track_id, visual=self._visual_payload(),
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
        if self.engine.position > 3.0:
            self.engine.seek(0.0)
            return
        if self.cfg.shuffle:
            self._play_index(self._shuffled_prev())
        elif self._index > 0:
            self._play_index(self._index - 1)
        else:
            self.engine.seek(0.0)

    def _on_track_end(self) -> None:
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

    def _seek_start(self, _e) -> None:
        self._seeking = True

    def _seek_end(self, _e) -> None:
        self._seeking = False
        self.engine.seek(self._progress.get() * self.engine.length)

    def _on_volume_change(self, val: float) -> None:
        self.engine.set_volume(val)
        self.cfg.volume = val

    def _toggle_shuffle(self) -> None:
        self.cfg.shuffle = not self.cfg.shuffle
        self._shuffle_order = []
        self._shuffle_btn.configure(
            text_color=ACCENT if self.cfg.shuffle else MUTED)

    def _cycle_repeat(self) -> None:
        modes = ["off", "all", "one"]
        self.cfg.repeat = modes[(modes.index(self.cfg.repeat) + 1) % len(modes)]
        self._repeat_btn.configure(
            text=self._repeat_icon(),
            text_color=MUTED if self.cfg.repeat == "off" else ACCENT)

    def _repeat_icon(self) -> str:
        return "🔂" if self.cfg.repeat == "one" else "🔁"

    # ══════════════════════════════════════════════════════════════════════════
    #  TICK — 500 ms
    # ══════════════════════════════════════════════════════════════════════════

    def _tick(self) -> None:
        try:
            self._update_progress()
            self._write_state()
            self._update_preview()
        except Exception:
            pass
        self.after(500, self._tick)

    def _update_progress(self) -> None:
        if self._seeking:
            return
        length, pos = self.engine.length, self.engine.position
        self._progress.set(pos / length if length > 0 else 0)
        self._pos_var.set(_fmt_time(pos))
        self._dur_var.set(_fmt_time(length))
        self._play_btn.configure(text="⏸" if self.engine.is_playing else "▶")

    def _visual_payload(self) -> dict:
        c = self.cfg
        return {
            "bg": c.ov_bg, "opacity": round(c.ov_opacity, 3),
            "blur": c.ov_blur, "radius": c.ov_radius, "width": c.ov_width,
            "accent": c.ov_accent, "title_color": c.ov_title_color,
            "artist_color": c.ov_artist_color, "title_size": c.ov_title_size,
            "artist_size": c.ov_artist_size, "show_cover": c.ov_show_cover,
            "show_progress": c.ov_show_progress, "transition": round(c.ov_transition, 3),
        }

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
                    duration=self.engine.length, position=self.engine.position,
                    playing=self.engine.is_playing, cover_src=cover,
                    shuffle=self.cfg.shuffle, repeat=self.cfg.repeat,
                    track_id=self._track_id, visual=self._visual_payload(),
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
            active = (i == self._index)
            label  = f"{'▶  ' if active else '     '}{title}"
            if artist:
                label += f"   —   {artist}"
            btn = ctk.CTkButton(
                self._queue_list, text=label,
                fg_color=ACCENT if active else SURF3,
                hover_color=ACCHOV if active else SURF,
                text_color=TEXT, anchor="w", height=32,
                corner_radius=6, font=("Segoe UI", 11),
                command=lambda idx=i: self._play_index(idx),
            )
            btn.grid(row=i, column=0, padx=4, pady=1, sticky="ew")

    def _refresh_folder_list(self) -> None:
        for w in self._folder_frame.winfo_children():
            w.destroy()
        for i, folder in enumerate(self.cfg.folders):
            row = ctk.CTkFrame(self._folder_frame, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew", pady=1)
            row.grid_columnconfigure(0, weight=1)

            name = Path(folder).name or folder
            ctk.CTkLabel(row, text=f"📂  {name}", text_color=TEXT,
                         font=("Segoe UI", 11), anchor="w").grid(
                row=0, column=0, sticky="w")

            override = self.cfg.folder_artists.get(folder, "")
            if override:
                ctk.CTkLabel(row, text=override, text_color=ACCLT,
                             font=("Segoe UI", 9), anchor="w").grid(
                    row=1, column=0, columnspan=3, sticky="w", pady=(0, 2))

            ctk.CTkButton(row, text="✎", width=24, height=24, corner_radius=4,
                          fg_color="transparent", hover_color=SURF3, text_color=MUTED,
                          font=("Segoe UI", 10),
                          command=lambda p=folder: self._set_folder_artist(p)).grid(
                row=0, column=1)
            ctk.CTkButton(row, text="✕", width=24, height=24, corner_radius=4,
                          fg_color="transparent", hover_color=DANGER, text_color=MUTED,
                          font=("Segoe UI", 10),
                          command=lambda p=folder: self._remove_folder(p)).grid(
                row=0, column=2)

    def _set_folder_artist(self, folder: str) -> None:
        dialog = ctk.CTkInputDialog(
            text=f"Artiste pour :\n{Path(folder).name}\n\n(vide = supprimer)",
            title="Artiste du dossier")
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
        if self._queue and self._index < len(self._queue):
            _, artist, _, _ = self._cached_meta(self._queue[self._index])
            self._artist_var.set(artist or "—")

    # ══════════════════════════════════════════════════════════════════════════
    #  COVER
    # ══════════════════════════════════════════════════════════════════════════

    def _update_cover(self, cover_path: str | None) -> None:
        try:
            if cover_path and Path(cover_path).exists():
                img = Image.open(cover_path).convert("RGB").resize(
                    (200, 200), Image.LANCZOS)
            else:
                img = _make_placeholder(200)
            self._cover_img = ImageTk.PhotoImage(img)
            self._cover_label.configure(image=self._cover_img, text="")
        except Exception:
            self._set_placeholder_cover()

    def _set_placeholder_cover(self) -> None:
        try:
            self._cover_img = ImageTk.PhotoImage(_make_placeholder(200))
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
            self.cfg.queue         = list(self._queue)
            self.cfg.queue_index   = self._index
            self.cfg.volume        = self.engine.volume
            self.cfg.window_geometry = self.geometry()
            self.cfg.save()
        except Exception:
            pass
        for fn in (write_stopped, self.engine.stop, self.server.shutdown, self.destroy):
            try:
                fn()
            except Exception:
                pass


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


def _blend_hex(fg: str, bg: str, alpha: float) -> str:
    def p(h: str) -> tuple[int, int, int]:
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    fr, fg_c, fb = p(fg)
    br, bg_c, bb = p(bg)
    r = int(br * (1 - alpha) + fr * alpha)
    g = int(bg_c * (1 - alpha) + fg_c * alpha)
    b = int(bb * (1 - alpha) + fb * alpha)
    return f"#{r:02x}{g:02x}{b:02x}"


def _draw_rrect(canvas: tk.Canvas, x0: int, y0: int, x1: int, y1: int,
                r: int, **kw) -> int:
    r = max(0, min(int(r), (x1 - x0) // 2 - 1, (y1 - y0) // 2 - 1))
    if r < 2:
        return canvas.create_rectangle(x0, y0, x1, y1, **kw)
    pts = [x0 + r, y0, x1 - r, y0, x1, y0 + r, x1, y1 - r,
           x1 - r, y1, x0 + r, y1, x0, y1 - r, x0, y0 + r]
    return canvas.create_polygon(pts, smooth=True, **kw)


def _trunc(text: str, max_px: int, font_size: int) -> str:
    limit = max(3, int(max_px / (font_size * 0.62)))
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _hsep(parent: ctk.CTkFrame, row: int, pady: tuple = (0, 0)) -> None:
    ctk.CTkFrame(parent, fg_color=BORDER, height=1).grid(
        row=row, column=0, sticky="ew", padx=0, pady=pady)
