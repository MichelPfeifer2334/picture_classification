# 📸 picture_classification – KI-Fotobuch aus Urlaubsbildern

Lokale Web-App, die Urlaubsfotos mit einem **lokalen Vision-Modell (Ollama)** bewertet,
**Duplikate, Serienbilder, ähnliche Motive und schwache Aufnahmen aussortiert** und die besten
Bilder chronologisch als **Fotobuch** zusammenstellt – mit kurzen Kapitelüberschriften,
manuellem Editor und druckfertigem PDF.

---

## Inhalt

- [Features](#features)
- [So funktioniert die Auswahl](#so-funktioniert-die-auswahl)
- [Architektur](#architektur)
- [Tech-Stack](#tech-stack)
- [Voraussetzungen](#voraussetzungen)
- [Schnellstart](#schnellstart)
- [Projektstruktur](#projektstruktur)
- [Konfiguration](#konfiguration)
- [Roadmap](#roadmap)
- [Dokumentation](#dokumentation)

---

## Features

| Feature | Status |
|---|---|
| Upload per Drag & Drop, Datei- oder Ordnerauswahl (JPG, PNG, HEIC, …) | ✅ |
| EXIF-Drehung und Aufnahmezeit, Thumbnails, verkleinerter Modell-Input | ✅ |
| KI-Bewertung wie ein Fotoredakteur: Score 1–10, Mängel, Stärken, Motiv, Personen, Bildschwerpunkt | ✅ |
| Common-Sense-Kriterien für Personen: Augen offen, nicht angeschnitten, freundlicher Ausdruck | ✅ |
| Technische Prüfung ohne KI: Schärfe, Belichtung | ✅ |
| Gruppen: Duplikate, Serienbilder, ähnliche Motive (z. B. 5× Eiffelturm) → das beste bleibt | ✅ |
| Regler „Strenge“ (Mindest-Score) und manuelles Aufnehmen/Aussortieren | ✅ |
| Mini-Kapitel entlang der Reise (EXIF-Zeit) mit kurzen KI-Überschriften | ✅ |
| Galerie als Urlaubsverlauf oder nach Kategorien | ✅ |
| Fotobuch-Layout: 1–4 Bilder/Seite, randlose Highlights, Zuschnitt um Gesichter/Motiv | ✅ |
| **Editor:** Bilder tauschen/verschieben/entfernen, Vorlagen, Seiten ordnen, Überschriften ändern | ✅ |
| Seitenvorschau im Browser = PDF | ✅ |
| Druck-PDF (Beschnittzugabe, 300 dpi), Text nur als Kapitelüberschrift | ✅ |
| Modernes dunkles UI (Glas-Optik, Animationen, Lightbox mit Tastatursteuerung) | ✅ |
| Seitenformat des konkreten Fotobuch-Anbieters | 🟡 Werte konfigurierbar, Anbieter offen |
| SQLite statt JSON, SSE statt Polling | 🟡 geplant |

## So funktioniert die Auswahl

```
Upload ──▶ Messwerte (Schärfe, Helligkeit, pHash, EXIF-Zeit)                ← ohne KI, sofort
Analyse ─▶ Modell: Kategorie · Score · Mängel · Stärken · Motiv · Personen · Schwerpunkt
Auswahl ─▶ Score − Abzüge + Boni → Gesamtscore 0–10; Rang = Score + Technik (Schärfe, Licht)
           Duplikate / Serien / ähnliche Motive gruppieren → das beste (ggf. zwei) bleibt
           Gesamtscore ≥ „Strenge“ → ins Buch (manuell übersteuerbar)
Kapitel ─▶ chronologisch; neues Kapitel bei > 90 min Pause oder neuem Tag
           Modell formuliert kurze Überschrift („Shopping in den Galeries Lafayette“)
Layout ──▶ Vorlage je Seite nach Seitenverhältnissen, Highlights randlos, Zuschnitt um das Motiv
Editor ──▶ manuelle Korrekturen per Drag & Drop
PDF ────▶ 300 dpi, Beschnittzugabe, Text nur als Kapitelüberschrift + Datum
```

Details: [docs/04-modell.md](docs/04-modell.md) (Bewertung) · [docs/06-pdf-fotobuch.md](docs/06-pdf-fotobuch.md) (Kapitel, Layout, Editor)

## Architektur

```
Vue 3 (:5173)  ──HTTP (Polling)──▶  FastAPI (:8000)  ──HTTP──▶  Ollama (:11434, GPU)
                                        │
                                        ├── data/albums/<id>/ (album.json + Bilder)
                                        ├── selection.py  (Score, Duplikate, Auswahl)
                                        ├── layout.py     (Seitenaufteilung)
                                        └── ReportLab ──▶ fotobuch.pdf
```

Details: [docs/02-architektur.md](docs/02-architektur.md)

## Tech-Stack

| Bereich | Technologie |
|---|---|
| Frontend | Vue 3, Vite, TypeScript – ohne UI-Bibliothek, eigenes CSS-Design |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2 (Ablage: JSON-Datei pro Album) |
| Python-Umgebung | Miniconda (Python-Version) + Poetry (Pakete) |
| Bildverarbeitung | Pillow, pillow-heif, imagehash, numpy |
| KI | Ollama mit `qwen2.5vl:7b` (Vergleich: `gemma3:12b`) |
| PDF | ReportLab |
| Qualität | pytest, ruff, mypy · vue-tsc |

## Voraussetzungen

- WSL2 (Ubuntu) oder Linux
- Miniconda, Poetry ≥ 2.0 (via pipx), Node.js ≥ 20.19, Ollama
- NVIDIA-GPU empfohlen (entwickelt auf RTX 4060 Ti, 16 GB VRAM)

## Schnellstart

> Ersteinrichtung Schritt für Schritt: **[docs/03-setup.md](docs/03-setup.md)**

Ollama läuft als Systemdienst. Dann in zwei Terminals:

```bash
# 1 – Backend
cd backend
conda activate fotobuch
poetry install                       # nur nach Änderungen an poetry.lock
uvicorn app.main:app --reload        # http://localhost:8000/docs

# 2 – Frontend
cd frontend
npm install                          # nur beim ersten Mal / nach Änderungen
npm run dev                          # http://localhost:5173
```

**VS Code:** Statt Terminal 1 geht auch `F5` → „Backend: FastAPI (uvicorn)“ (`.vscode/launch.json`,
mit Breakpoints). VS Code dafür aus WSL mit `code .` öffnen.

Bedienung: Bilder hochladen → **Analyse starten** → Auswahl prüfen (Regler „Strenge“, ＋/✓ auf den
Karten, Klick öffnet die Lightbox) → optional **✎ Buch bearbeiten** → **PDF exportieren**.

Tests & Checks:

```bash
cd backend && pytest && ruff check . && mypy app
cd frontend && npm run type-check
```

## Projektstruktur

```
picture_classification/
├── README.md               ← dieses Dokument (immer aktuell halten!)
├── CLAUDE.md               ← Arbeitsregeln für Claude Code
├── .vscode/                launch.json (Backend starten/debuggen), empfohlene Extensions
├── docs/                   ← Projektdokumentation
│   ├── 01-vision.md        Ziel & Anforderungen
│   ├── 02-architektur.md   Komponenten, Datenfluss, Datenmodell
│   ├── 03-setup.md         Setup-Anleitung (conda, Poetry, Ollama, Vue)
│   ├── 04-modell.md        Ollama, Prompt, Bewertung & Auswahl-Logik
│   ├── 05-api.md           API-Endpunkte
│   ├── 06-pdf-fotobuch.md  Layout-Vorlagen, Druckvorgaben
│   └── adr/                Architekturentscheidungen
├── backend/
│   ├── environment.yml     conda-Env (nur Python 3.12)
│   ├── pyproject.toml      Poetry-Projekt & Tool-Konfiguration
│   ├── poetry.toml         Poetry → conda-Env (kein eigenes venv)
│   ├── poetry.lock
│   ├── .env.example        Konfigurationsvorlage
│   ├── app/
│   │   ├── main.py         FastAPI-App
│   │   ├── core/config.py  Einstellungen (Modell, Kategorien, Auswahl, Layout)
│   │   ├── api/            health.py, albums.py, deps.py
│   │   ├── models/album.py Datenmodelle (Album, ImageRecord, Classification, Metrics)
│   │   └── services/
│   │       ├── storage.py            Ablage pro Album (JSON + Dateien)
│   │       ├── image_processing.py   EXIF, Thumbnails, Schärfe/Belichtung/pHash
│   │       ├── classifier/           Interface + Ollama-Implementierung (Prompt)
│   │       ├── jobs.py               Hintergrund-Analyse
│   │       ├── selection.py          Score, Abzüge/Boni, Gruppen, Auswahl
│   │       ├── chapters.py           Mini-Kapitel entlang der Reise
│   │       ├── layout.py             Fotobuch-Seitenaufteilung (automatisch + manuell)
│   │       └── pdf/export.py         Druck-PDF (ReportLab)
│   └── tests/
├── frontend/
│   ├── package.json        Vue 3, Vite, TypeScript
│   ├── vite.config.ts      Proxy /api → :8000
│   └── src/
│       ├── App.vue         Seitenaufbau
│       ├── useAlbum.ts     App-Zustand & Aktionen
│       ├── api.ts, types.ts, labels.ts
│       ├── style.css       Design-Tokens & Basis-Styles
│       └── components/     AppHeader, UploadZone, AnalysisPanel, SelectionBar,
│                           PhotoCard, ScoreRing, Lightbox, BookPreview, BookPageView,
│                           BookEditor, ToastStack
└── data/                   Alben, Fotos, Exporte (nicht im Git)
```

## Konfiguration

`backend/.env` (Vorlage: `backend/.env.example`). Alle Werte haben sinnvolle Standards:

| Variable | Standard | Bedeutung |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Adresse des Ollama-Servers |
| `OLLAMA_MODEL` | `qwen2.5vl:7b` | Vision-Modell |
| `OLLAMA_TIMEOUT_S` | `180` | Max. Wartezeit pro Bild |
| `DATA_DIR` | `../data` | Ablage für Alben, Fotos, Exporte |
| `CATEGORIES` | `["strand","landschaft","stadt","essen","personen","tiere","sonstiges"]` | Kategorien = Kapitel (letzte = Fallback) |
| `DEFAULT_MIN_SCORE` | `6.0` | Start-Strenge neuer Alben |
| `DUP_HAMMING` | `8` | pHash-Abstand für Duplikate (kleiner = strenger) |
| `BURST_HAMMING` / `BURST_SECONDS` | `20` / `4` | Serienbilder: ähnlich **und** zeitnah |
| `BLUR_ABS` / `BLUR_REL` | `15` / `0.25` | Unschärfe: absolut bzw. relativ zum Album-Median |
| `SCENE_MINUTES` | `30` | Ähnliches Motiv: gleiches Motiv innerhalb dieser Zeit |
| `SIMILAR_KEEP` / `SIMILAR_KEEP_MARGIN` | `2` / `0.5` | max. Bilder je Motiv-Gruppe, wenn fast gleich gut |
| `CHAPTER_GAP_MINUTES` | `90` | Pause, ab der ein neues Kapitel beginnt |
| `CHAPTER_MAX_IMAGES` / `CHAPTER_MIN_IMAGES` | `30` / `3` | Kapitel teilen / ab wie vielen Bildern eine Überschrift |
| `TITLE_BAND_MM` | `16` | Platz für die Überschrift auf der ersten Kapitelseite |
| `PAGE_WIDTH_MM` / `PAGE_HEIGHT_MM` | `297` / `210` | Endformat des Buchs |
| `BLEED_MM` / `MARGIN_MM` / `GUTTER_MM` | `3` / `12` / `4` | Beschnitt, Rand, Bildabstand |
| `PRINT_DPI` | `300` | Auflösung der Bilder im PDF |
| `HERO_MIN_SCORE` | `8.5` | ab hier randlose Ganzseite (Querformat) |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Erlaubte Frontend-Origins |

## Roadmap

| Phase | Inhalt | Status |
|---|---|---|
| 0 – Setup | conda, Poetry, Vue-Gerüst, Ollama + Modell, Doku | ✅ |
| MVP | Upload → Klassifizierung → Galerie → schlichtes PDF | ✅ |
| Auswahl & Design | Score + Abzüge, Duplikate/Serien, Strenge-Regler, Review, neues UI | ✅ |
| Fotobuch-Layout | Vorlagen, Highlight-Seiten, Vorschau, Druck-PDF | ✅ |
| Story & Editor | Common-Sense-Kriterien, ähnliche Motive, Kapitel + Überschriften, Editor | ✅ Code fertig, Praxistest ausstehend |
| 1 – Kalibrierung | Schwellwerte & Prompt an echten Fotos justieren, Modellvergleich | ⏳ |
| 5 – Anbieterformat | Format/Seitenzahl des Fotobuch-Anbieters, Umschlag | ⏳ |
| 6 – Feinschliff | Undo im Editor, Umschlag, SQLite, SSE, optional SigLIP | ⏳ |

## Dokumentation

Alle Details in [`docs/`](docs/). Architekturentscheidungen in [`docs/adr/`](docs/adr/).
