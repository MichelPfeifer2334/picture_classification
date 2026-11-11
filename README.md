# Bildklassifikation

Lokale Web-App, die Fotos mit einem **lokalen Vision-Modell (Ollama)** kategorisiert,
**gute von schlechten Bildern** trennt, Bildunterschriften vorschlägt und daraus ein
**druckfertiges Fotobuch-PDF** erzeugt – damit ich das Aussortieren nicht selbst machen muss.

---

## Inhalt

- [Features](#features)
- [Architektur](#architektur)
- [Tech-Stack](#tech-stack)
- [Voraussetzungen](#voraussetzungen)
- [Schnellstart](#schnellstart)
- [Projektstruktur](#projektstruktur)
- [Roadmap](#roadmap)
- [Dokumentation](#dokumentation)

---

## Features

| Feature | Status |
|---|---|
| Health-Check Backend ↔ Ollama (inkl. Modell-Verfügbarkeit) | ✅ MVP |
| Upload vieler Fotos per Drag & Drop, Datei- oder Ordnerauswahl (JPG, PNG, HEIC, …) | ✅ MVP |
| EXIF-Drehung, Thumbnails, verkleinerter Modell-Input | ✅ MVP |
| Kategorisierung per lokalem Vision-Modell (`qwen2.5vl:7b`) mit Fortschrittsanzeige | ✅ MVP |
| Qualitätsbewertung gut / ok / schlecht + Bildunterschrift | ✅ MVP |
| Galerie gruppiert nach Kategorie | ✅ MVP |
| Schlichter PDF-Export (A4, 1 Bild/Seite, optional ohne schlechte Bilder) | ✅ MVP |
| EXIF-Datum/GPS auswerten, chronologische Sortierung | 🟡 geplant |
| Duplikat- & Unschärfeerkennung | 🟡 geplant |
| Review: Kategorie ändern, Bilder ausschließen, Captions bearbeiten | 🟡 geplant |
| PDF im Format des Fotobuch-Anbieters (Layouts, Beschnitt) | 🟡 geplant |

## Architektur

```
Vue 3 (:5173)  ──HTTP (Polling)──▶  FastAPI (:8000)  ──HTTP──▶  Ollama (:11434, GPU)
                                        │
                                        ├── data/albums/<id>/ (album.json + Bilder)
                                        └── ReportLab ──▶ fotobuch.pdf
```

Details: [docs/02-architektur.md](docs/02-architektur.md)

## Tech-Stack

| Bereich | Technologie |
|---|---|
| Frontend | Vue 3, Vite, TypeScript (MVP: eine Seite; Pinia/Router später) |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic v2 (MVP: JSON-Dateien, später SQLModel/SQLite) |
| Python-Umgebung | Miniconda (Python-Version) + Poetry (Pakete) |
| Bildverarbeitung | Pillow, pillow-heif, imagehash |
| KI | Ollama mit `qwen2.5vl:7b` (Vergleich: `gemma3:12b`) |
| PDF | ReportLab |
| Qualität | pytest, ruff, mypy · vue-tsc |

## Voraussetzungen

- WSL2 (Ubuntu) oder Linux
- Miniconda, Poetry ≥ 2.0 (via pipx), Node.js ≥ 20, Ollama
- NVIDIA-GPU empfohlen (entwickelt auf RTX 4060 Ti, 16 GB VRAM)

## Schnellstart

> Ersteinrichtung Schritt für Schritt: **[docs/03-setup.md](docs/03-setup.md)**

Nach der Einrichtung, in drei Terminals:

```bash
# 1 – Modell-Server
ollama serve

# 2 – Backend
cd backend
conda activate fotobuch
poetry install                       # nur nach Änderungen an poetry.lock
uvicorn app.main:app --reload        # http://localhost:8000/docs

# 3 – Frontend
cd frontend
npm install                          # nur beim ersten Mal / nach Änderungen
npm run dev                          # http://localhost:5173
```

**VS Code:** Statt Terminal 2 geht auch `F5` → „Backend: FastAPI (uvicorn)“ (`.vscode/launch.json`,
mit Breakpoints). VS Code dafür aus WSL mit `code .` öffnen.

Bedienung: Bilder hochladen → „Bilder klassifizieren“ → „PDF herunterladen“.

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
├── docs/                   ← Projektdokumentation
│   ├── 01-vision.md        Ziel & Anforderungen
│   ├── 02-architektur.md   Komponenten, Datenfluss, Datenmodell
│   ├── 03-setup.md         Setup-Anleitung (conda, Poetry, Ollama, Vue)
│   ├── 04-modell.md        Ollama, Hugging Face, Modellwahl, Prompt
│   ├── 05-api.md           API-Endpunkte
│   ├── 06-pdf-fotobuch.md  Druckvorgaben & PDF-Layout
│   └── adr/                Architekturentscheidungen
├── backend/
│   ├── environment.yml     conda-Env (nur Python 3.12)
│   ├── pyproject.toml      Poetry-Projekt & Tool-Konfiguration
│   ├── poetry.toml         Poetry → conda-Env (kein eigenes venv)
│   ├── poetry.lock
│   ├── .env.example        Konfigurationsvorlage
│   ├── app/
│   │   ├── main.py         FastAPI-App
│   │   ├── core/config.py  Einstellungen (Modell, Kategorien, Pfade)
│   │   ├── api/            health.py, albums.py, deps.py
│   │   ├── models/album.py Datenmodelle (Album, ImageRecord, Classification)
│   │   └── services/
│   │       ├── storage.py            Ablage pro Album (JSON + Dateien)
│   │       ├── image_processing.py   EXIF-Drehung, Thumbnails, Modell-Input
│   │       ├── jobs.py               Hintergrund-Klassifizierung
│   │       ├── classifier/           Interface + Ollama-Implementierung
│   │       └── pdf/export.py         PDF-Export (ReportLab)
│   └── tests/
├── frontend/
│   ├── package.json        Vue 3, Vite, TypeScript
│   ├── vite.config.ts      Proxy /api → :8000
│   └── src/
│       ├── App.vue         Seite: Upload → Klassifizieren → Export → Galerie
│       ├── api.ts, types.ts
│       └── components/     UploadZone.vue, ImageCard.vue
└── data/                   Alben, Fotos, Exporte (nicht im Git)
```

## Roadmap

| Phase | Inhalt | Status |
|---|---|---|
| 0 – Setup | conda, Poetry, Vue-Gerüst, Ollama + Modell, Doku | ✅ |
| MVP | Upload → Klassifizierung (Ollama) → Galerie → schlichtes PDF | ✅ Code fertig, Praxistest ausstehend |
| 1 – Modell-Spike | 20 Testfotos, Prompt, Modellvergleich | ⏳ |
| 2 – Upload & Speicher | EXIF-Datum/GPS, SQLite statt JSON | ⏳ |
| 3 – Klassifizierung | SSE statt Polling, Abbrechen/Neustart | ⏳ |
| 4 – Review-UI | Umsortieren, Aussortieren, Captions | ⏳ |
| 5 – PDF-Export | Anbieterformat, Layouts, Beschnitt, 300 dpi | ⏳ |
| 6 – Feinschliff | Tests, Fehlerbehandlung, optional SigLIP | ⏳ |

## Dokumentation

Alle Details in [`docs/`](docs/). Architekturentscheidungen in [`docs/adr/`](docs/adr/).

## Konfiguration

`backend/.env` (Vorlage: `backend/.env.example`):

| Variable | Standard | Bedeutung |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Adresse des Ollama-Servers |
| `OLLAMA_MODEL` | `qwen2.5vl:7b` | Verwendetes Vision-Modell |
| `OLLAMA_TIMEOUT_S` | `180` | Max. Wartezeit pro Bild |
| `DATA_DIR` | `../data` | Ablage für Alben, Fotos, Exporte |
| `CATEGORIES` | `["strand","landschaft","stadt","essen","personen","tiere","sonstiges"]` | Erlaubte Kategorien (letzte = Fallback) |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Erlaubte Frontend-Origins |
