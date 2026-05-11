# TAC Players Music Overlay

<div align="center">

**Lecteur audio local avec overlay en temps réel pour OBS Studio.**

Lance ta musique, vois le titre s'afficher sur ton stream — sans compte, sans cloud, sans prise de tête.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter-1F6AA5?style=flat-square)
![OBS](https://img.shields.io/badge/OBS-Browser%20Source-302E31?style=flat-square&logo=obsstudio&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows-0078D4?style=flat-square&logo=windows&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-7c3aed?style=flat-square)

</div>

---

## Comment ça marche

```
Python (moteur)          OBS Studio
──────────────           ──────────────────────────────
Lis ta musique    ──►   Browser Source
Écrit le JSON     ──►   http://localhost:8080/overlay/
Copie la cover    ──►   Overlay HTML/CSS transparent
```

Tu contrôles la lecture dans l'app Python.
L'overlay s'affiche dans OBS avec fond transparent, sans fenêtre visible sur le stream.

---

## Fonctionnalités

### Panneau de contrôle
- **Dossiers** — ajoute n'importe quel dossier, scan récursif automatique
- **Artiste personnalisé par dossier** — bouton ✎ pour définir l'artiste affiché (groupes, collabs...)
- **File d'attente** — double-clic pour jouer, navigation prev/next
- **Transport complet** — play/pause, seek, volume, shuffle, repeat (off/one/all)
- **Bouton Rafraîchir** — force la mise à jour de l'overlay instantanément

### Overlay OBS
- Fond transparent natif (pas de chroma key)
- Cover art avec transition fade au changement de titre
- Titre, artiste, barre de progression animée
- Se met à jour automatiquement à chaque nouvelle musique

### Formats supportés
`MP3` `WAV` `FLAC` `OGG` `M4A` `AIFF` `AAC`

---

## Installation

**Prérequis :** Python 3.11+

```bash
git clone https://github.com/Lekarov/TAC-Players-Music-Overlay.git
cd TAC-Players-Music-Overlay
```

Double-clic sur `launch.bat` — installe les dépendances et lance l'app automatiquement.

Ou manuellement :
```bash
pip install -r requirements.txt
python main.py
```

---

## Configuration OBS

1. Dans OBS → **Sources** → **+** → **Navigateur**
2. Cocher **Fichier local** ou entrer l'URL :
   ```
   http://localhost:8080/overlay/index.html
   ```
3. Largeur : `420` / Hauteur : `120`
4. Cocher **Actualiser le navigateur quand la scène devient active**

---

## Cover art

La cover est détectée automatiquement dans le dossier de la musique.
Noms reconnus : `cover.png`, `cover.jpg`, `folder.jpg`, `artwork.png`...

---

## Structure

```
TAC-Players-Music-Overlay/
├── main.py                    Point d'entrée + serveur HTTP local
├── launch.bat                 Lanceur Windows (installe deps + lance)
├── requirements.txt
├── overlay/
│   ├── index.html             Source OBS
│   ├── style.css              Design glassmorphism
│   └── script.js              Polling JSON + interpolation progression
└── src/
    ├── core/
    │   ├── config.py          Persistance JSON (AppData)
    │   └── scanner.py         Scan récursif dossiers audio
    ├── player/
    │   ├── engine.py          Moteur audio (pygame-ce)
    │   └── writer.py          Écrit now_playing.json + cover.jpg
    └── ui/
        └── control.py         Interface de contrôle (customtkinter)
```

---

## Stack

```
customtkinter    Interface dark theme moderne
pygame-ce        Lecture audio (compatible Python 3.12+)
mutagen          Lecture métadonnées ID3/FLAC
Pillow           Traitement et redimensionnement cover art
```

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

Développé par **Pestovich**

</div>
