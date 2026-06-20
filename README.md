<div align="center">

# 🎵 TAC Players Music Overlay

**Lecteur audio local avec overlay Now Playing en temps réel pour OBS Studio.**

Lance ta musique, personnalise l'overlay, vois le titre s'afficher sur ton stream —
sans compte, sans cloud, sans prise de tête.

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-1F6AA5?style=flat-square)](https://github.com/TomSchimansky/CustomTkinter)
[![OBS](https://img.shields.io/badge/OBS-Browser%20Source-302E31?style=flat-square&logo=obsstudio&logoColor=white)](https://obsproject.com/)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows&logoColor=white)](https://www.microsoft.com/windows)
[![License](https://img.shields.io/badge/License-MIT-7c3aed?style=flat-square)](LICENSE)

</div>

---

## Comment ça marche

```
Panneau de contrôle (Python)        OBS Studio
────────────────────────────        ─────────────────────────────────
  Lecture audio locale       ──►    Browser Source
  Écriture now_playing.json  ──►    http://localhost:8080/overlay/
  Copie cover.jpg            ──►    Overlay HTML/CSS transparent
  Réglages visuels           ──►    CSS custom properties en live
```

Tu contrôles tout depuis l'interface Python.
L'overlay se met à jour en moins d'une seconde dans OBS, fond transparent natif — aucune fenêtre visible sur le stream.

---

## Fonctionnalités

### Panneau de contrôle

| Fonction | Détail |
|---|---|
| **Dossiers** | Ajout par dossier ou fichier, scan récursif automatique |
| **Artiste par dossier** | Bouton ✎ pour définir l'artiste affiché (groupes, collabs) |
| **File d'attente** | Navigation cliquable, highlight piste active, vider la queue |
| **Transport** | Play / Pause / Seek / Volume / Shuffle / Repeat (off · one · all) |
| **Rafraîchir** | Force la mise à jour immédiate de l'overlay |

### Overlay OBS

- Fond transparent natif (aucun chroma key nécessaire)
- Cover art avec transition **fade** au changement de piste
- Titre, artiste, barre de progression animée (interpolation 200 ms)
- Toutes les propriétés visuelles pilotées par CSS custom properties

### Réglages visuels — onglet *Overlay Visuel*

Accède au panneau de réglage directement dans l'interface, avec **preview live** de l'overlay.

#### Thèmes prédéfinis

| Thème | Ambiance |
|---|---|
| **Glassmorphism** | Fond semi-transparent, blur, accent violet — défaut |
| **Dark Minimal** | Très sombre, sans blur, texte blanc pur |
| **Neon** | Noir profond, texte et accent vert néon |
| **Sakura** | Mauve profond, teintes roses/violettes douces |

#### Paramètres ajustables en temps réel

**Apparence**
- Opacité du fond (5 – 100 %)
- Flou (blur) (0 – 40 px)
- Rayon des coins (0 – 40 px)
- Largeur de l'overlay (280 – 700 px)

**Couleurs** — colorpicker OS natif pour chaque élément
- Couleur de fond · Accent · Titre · Artiste

**Typographie**
- Taille du titre (9 – 26 px)
- Taille de l'artiste (8 – 22 px)

**Éléments visibles**
- Afficher / masquer la pochette d'album
- Afficher / masquer la barre de progression

**Animations**
- Vitesse de transition CSS (0.05 – 1.2 s)

Tous les réglages sont **persistés** dans `AppData` et propagés vers OBS en moins d'une seconde.

### Formats audio supportés

`MP3` · `WAV` · `FLAC` · `OGG` · `M4A` · `AIFF` · `AAC`

---

## Installation

**Prérequis :** Python 3.11+

```bash
git clone https://github.com/Lekarov/TAC-Players-Music-Overlay.git
cd TAC-Players-Music-Overlay
```

**Démarrage rapide — double-clic sur `launch.bat`**
> Installe les dépendances et lance l'application automatiquement.

Ou manuellement :

```bash
pip install -r requirements.txt
python main.py
```

---

## Configuration OBS

1. Dans OBS → **Sources** → **+** → **Navigateur**
2. Entrer l'URL :
   ```
   http://localhost:8080/overlay/index.html
   ```
3. Largeur : `420` — Hauteur : `120` *(ajuste selon la largeur configurée)*
4. Cocher **Actualiser le navigateur quand la scène devient active**

> **Astuce :** le bouton **Copier URL** dans la sidebar copie l'URL directement dans le presse-papier.

---

## Cover art

La pochette est détectée automatiquement dans le dossier de la piste.
Noms de fichiers reconnus : `cover.png` `cover.jpg` `folder.jpg` `artwork.png` `front.jpg` …

---

## Structure du projet

```
TAC-Players-Music-Overlay/
├── main.py                    Point d'entrée + serveur HTTP local
├── launch.bat                 Lanceur Windows (installe deps + lance)
├── requirements.txt
├── data/
│   ├── now_playing.json       État temps réel (titre, position, réglages visuels)
│   └── cover.jpg              Pochette de la piste en cours
├── overlay/
│   ├── index.html             Source navigateur OBS
│   ├── style.css              Design — CSS custom properties
│   └── script.js              Polling JSON + interpolation + application des visuels
└── src/
    ├── core/
    │   ├── config.py          Persistance JSON (AppData) — incl. réglages overlay
    │   └── scanner.py         Scan récursif dossiers audio + détection cover
    ├── player/
    │   ├── engine.py          Moteur audio (pygame-ce)
    │   └── writer.py          Écrit now_playing.json + cover.jpg
    └── ui/
        └── control.py         Interface (customtkinter) — nav, preview, réglages
```

---

## Stack technique

| Bibliothèque | Rôle |
|---|---|
| `customtkinter` | Interface dark theme moderne |
| `pygame-ce` | Lecture audio multi-format (Python 3.12+ compatible) |
| `mutagen` | Lecture métadonnées ID3 / FLAC / MP4 |
| `Pillow` | Traitement et redimensionnement de la cover art |

---

## Contributors

<table>
  <tr>
    <td align="center">
      <a href="https://github.com/Pestovich">
        <img src="https://github.com/Pestovich.png" width="80px" alt="Pestovich"/><br/>
        <sub><b>Pestovich</b></sub>
      </a><br/>
      <sub>Créateur & développeur principal</sub>
    </td>
  </tr>
</table>

---

<div align="center">

Développé par **Pestovich** · 🎮 [twitch.tv/Pestovich](https://twitch.tv/Pestovich)

</div>
