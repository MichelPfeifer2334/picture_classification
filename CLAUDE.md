# CLAUDE.md – Arbeitsregeln für dieses Projekt

## Projekt

Lokale Web-App: Urlaubsfotos hochladen → per Ollama-Vision-Modell kategorisieren und
Qualität bewerten → Review → Fotobuch-PDF. Details: `README.md`, `docs/`.

## Dokumentationspflicht (wichtig!)

- **`README.md` wird bei jeder relevanten Änderung mitgepflegt**: Features-Tabelle, Roadmap-Status,
  Projektstruktur, Schnellstart, Konfiguration.
- Passende Datei in `docs/` aktualisieren:
  - Setup/Tooling geändert → `docs/03-setup.md`
  - Architektur/Datenmodell → `docs/02-architektur.md`
  - Modell/Prompt → `docs/04-modell.md`
  - Endpunkt hinzugefügt/geändert → `docs/05-api.md`
  - PDF/Druck → `docs/06-pdf-fotobuch.md`
- Größere Entscheidungen als neue ADR in `docs/adr/` festhalten.
- Doku ist auf **Deutsch**.

## Umgebung

- Python 3.12 aus conda-Env `fotobuch`; Pakete **nur** über Poetry (`poetry add`), nie `pip install`/`conda install`.
- Poetry legt kein venv an (`backend/poetry.toml`: `virtualenvs.create = false`).
- Frontend: Vue 3 + Vite + TS in `frontend/`, Paketmanager npm.
- Ollama läuft auf `localhost:11434`, Startmodell `qwen2.5vl:7b`, GPU: RTX 4060 Ti 16 GB.
- **Nichts selbst installieren oder Setup-Befehle ausführen, ohne dass der User es ausdrücklich verlangt.**
  Der User richtet die Umgebung selbst ein.

## Konventionen

- Backend: Router in `app/api/`, Logik in `app/services/`, Modelle in `app/models/`.
- Classifier immer über das Interface in `app/services/classifier/`.
- Auswahl-Logik in `app/services/selection.py` (nach Änderungen immer `curate()` aufrufen),
  Kapitel in `app/services/chapters.py`, Fotobuch-Layout in `app/services/layout.py`.
- Fotobuch-PDF: Bilder im Vordergrund; Text nur als kurze Kapitelüberschrift + Datum.
- Frontend ohne externe Fonts/CDNs (Privatsphäre: alles lokal); Zustand in `src/useAlbum.ts`.
- Prüfen: `pytest`, `ruff check .`, `mypy app` (Backend) · `npm run type-check` (Frontend).
