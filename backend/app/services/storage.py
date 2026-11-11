"""Dateibasierte Ablage: ein Ordner pro Album mit album.json und den Bilddateien.

data/albums/<album_id>/
├── album.json
├── full/<image_id>.jpg         normalisiert (EXIF-gedreht, RGB) – Quelle fürs PDF
├── model_input/<image_id>.jpg  verkleinert fürs Modell
├── thumbs/<image_id>.webp      Vorschaubild fürs Frontend
└── export/fotobuch.pdf
"""

import asyncio
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from app.models.album import Album

_ID_RE = re.compile(r"^[0-9a-f]{32}$")


class AlbumNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class ImagePaths:
    full: Path
    model_input: Path
    thumb: Path


class AlbumStore:
    def __init__(self, data_dir: Path) -> None:
        self.root = data_dir.resolve() / "albums"
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}

    # --- IDs & Pfade ---------------------------------------------------------

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    def album_dir(self, album_id: str) -> Path:
        # Schutz vor Path-Traversal: nur gültige Hex-IDs erlaubt
        if not _ID_RE.match(album_id):
            raise AlbumNotFoundError(album_id)
        return self.root / album_id

    def image_paths(self, album_id: str, image_id: str) -> ImagePaths:
        if not _ID_RE.match(image_id):
            raise AlbumNotFoundError(image_id)
        base = self.album_dir(album_id)
        return ImagePaths(
            full=base / "full" / f"{image_id}.jpg",
            model_input=base / "model_input" / f"{image_id}.jpg",
            thumb=base / "thumbs" / f"{image_id}.webp",
        )

    def export_path(self, album_id: str) -> Path:
        return self.album_dir(album_id) / "export" / "fotobuch.pdf"

    # --- Lesen/Schreiben -----------------------------------------------------

    def create(self) -> Album:
        album = Album(id=self.new_id())
        base = self.album_dir(album.id)
        for sub in ("full", "model_input", "thumbs", "export"):
            (base / sub).mkdir(parents=True, exist_ok=True)
        self.save(album)
        return album

    def get(self, album_id: str) -> Album:
        path = self.album_dir(album_id) / "album.json"
        if not path.exists():
            raise AlbumNotFoundError(album_id)
        return Album.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, album: Album) -> None:
        path = self.album_dir(album.id) / "album.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(album.model_dump_json(indent=2), encoding="utf-8")
        tmp.replace(path)  # atomar ersetzen, damit nie eine halbe Datei entsteht

    @asynccontextmanager
    async def locked(self, album_id: str) -> AsyncIterator[Album]:
        """Lesen-Ändern-Speichern unter Lock, damit Upload und Klassifizierung sich
        nicht gegenseitig Änderungen überschreiben."""
        lock = self._locks.setdefault(album_id, asyncio.Lock())
        async with lock:
            album = self.get(album_id)
            yield album
            self.save(album)
