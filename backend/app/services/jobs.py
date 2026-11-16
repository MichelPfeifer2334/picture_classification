"""Hintergrund-Job: analysiert die Bilder eines Albums nacheinander, danach Kapitelüberschriften.

Nacheinander, weil die GPU ohnehin nur ein Bild gleichzeitig effizient verarbeitet.
Der Fortschritt steht in album.job und wird vom Frontend per Polling abgefragt.
"""

import asyncio
import logging
from datetime import UTC, datetime

from app.core.config import Settings
from app.models.album import ImageStatus, JobState
from app.services.chapters import fallback_title
from app.services.classifier.base import Classifier
from app.services.image_processing import metrics_from_file
from app.services.selection import curate
from app.services.storage import AlbumStore

log = logging.getLogger(__name__)

SELECTION_EVERY = 5  # Auswahl während des Laufs alle n Bilder neu berechnen


class ClassificationRunner:
    def __init__(self, store: AlbumStore, classifier: Classifier, settings: Settings) -> None:
        self._store = store
        self._classifier = classifier
        self._settings = settings
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def is_running(self, album_id: str) -> bool:
        task = self._tasks.get(album_id)
        return task is not None and not task.done()

    async def start(self, album_id: str, force: bool = False) -> JobState:
        """Startet die Analyse. force=True bewertet auch schon klassifizierte Bilder neu."""
        if self.is_running(album_id):
            return self._store.get(album_id).job

        async with self._store.locked(album_id) as album:
            pending = [
                img.id for img in album.images if force or img.status != ImageStatus.CLASSIFIED
            ]
            album.job = JobState(status="running", total=len(pending), started_at=datetime.now(UTC))
            job = album.job

        self._tasks[album_id] = asyncio.create_task(self._run(album_id, pending, force))
        return job

    async def _run(self, album_id: str, image_ids: list[str], force: bool) -> None:
        try:
            for n, image_id in enumerate(image_ids, start=1):
                await self._analyze_one(album_id, image_id, n)
            await self._name_chapters(album_id, force)
            await self._name_album(album_id, force)
        finally:
            async with self._store.locked(album_id) as album:
                album.job.status = "done"
                curate(album, self._settings)
            self._tasks.pop(album_id, None)

    async def _analyze_one(self, album_id: str, image_id: str, n: int) -> None:
        paths = self._store.image_paths(album_id, image_id)
        metrics = None
        try:
            img = self._store.get(album_id).find_image(image_id)
            if img is not None and img.metrics is None:  # ältere Uploads nachrüsten
                metrics = await asyncio.to_thread(metrics_from_file, paths.model_input)
            result = await self._classifier.classify(paths.model_input)
            error = None
        except Exception as exc:
            log.exception("Analyse fehlgeschlagen: %s", image_id)
            result, error = None, f"{type(exc).__name__}: {exc}"

        async with self._store.locked(album_id) as album:
            img = album.find_image(image_id)
            if img is not None:
                if metrics is not None:
                    img.metrics = metrics
                if result is not None:
                    img.classification = result
                img.error = error
                img.status = ImageStatus.ERROR if error else ImageStatus.CLASSIFIED
            album.job.done += 1
            if n % SELECTION_EVERY == 0:
                curate(album, self._settings)

    async def _name_chapters(self, album_id: str, force: bool) -> None:
        """Kapitelüberschriften per Modell – nur für Kapitel ohne (oder mit veraltetem) Titel."""
        async with self._store.locked(album_id) as album:
            curate(album, self._settings)
            album.job.phase = "titles"
            by_id = {img.id: img for img in album.images}
            todo = []
            for chapter in album.chapters:
                if chapter.title_edited or (chapter.title and not force):
                    continue
                imgs = [by_id[i] for i in chapter.image_ids if i in by_id]
                imgs = [i for i in imgs if i.classification]
                if imgs:
                    todo.append((chapter.id, imgs))

        for chapter_id, imgs in todo:
            ranked = sorted(imgs, key=lambda i: (not i.included, -(i.rank or 0)))
            descriptions = [
                f"{i.classification.subject} – {i.classification.caption}"
                for i in ranked
                if i.classification
            ]
            try:
                title = await self._classifier.chapter_title(descriptions)
            except Exception:
                log.exception("Kapitelüberschrift fehlgeschlagen: %s", chapter_id)
                title = ""
            title = title or fallback_title(imgs)
            async with self._store.locked(album_id) as album:
                target = album.find_chapter(chapter_id)
                if target is not None and not target.title_edited:
                    target.title = title

    async def _name_album(self, album_id: str, force: bool) -> None:
        """Albumtitel-Vorschlag ("Paris") aus Kapitelüberschriften und Motiven."""
        album = self._store.get(album_id)
        if album.suggested_title and not force:
            return
        chapter_titles = [f"Kapitel: {c.title}" for c in album.chapters if c.title]
        best = sorted(
            (i for i in album.images if i.included and i.classification),
            key=lambda i: -(i.rank or 0),
        )[:12]
        motifs = [
            f"Motiv: {i.classification.subject} – {i.classification.caption}"
            for i in best
            if i.classification
        ]
        descriptions = chapter_titles + motifs
        if not descriptions:
            return
        try:
            title = await self._classifier.album_title(descriptions)
        except Exception:
            log.exception("Albumtitel fehlgeschlagen: %s", album_id)
            return
        if title:
            async with self._store.locked(album_id) as locked:
                locked.suggested_title = title
