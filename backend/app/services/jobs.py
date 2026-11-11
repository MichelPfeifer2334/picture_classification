"""Hintergrund-Job: klassifiziert alle noch offenen Bilder eines Albums nacheinander.

Nacheinander, weil die GPU ohnehin nur ein Bild gleichzeitig effizient verarbeitet.
Der Fortschritt steht in album.job und wird vom Frontend per Polling abgefragt.
"""

import asyncio
import logging

from app.models.album import ImageStatus, JobState
from app.services.classifier.base import Classifier
from app.services.storage import AlbumStore

log = logging.getLogger(__name__)


class ClassificationRunner:
    def __init__(self, store: AlbumStore, classifier: Classifier) -> None:
        self._store = store
        self._classifier = classifier
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def is_running(self, album_id: str) -> bool:
        task = self._tasks.get(album_id)
        return task is not None and not task.done()

    async def start(self, album_id: str) -> JobState:
        if self.is_running(album_id):
            return self._store.get(album_id).job

        async with self._store.locked(album_id) as album:
            pending = [img.id for img in album.images if img.status != ImageStatus.CLASSIFIED]
            album.job = JobState(status="running" if pending else "done", total=len(pending))
            job = album.job

        if pending:
            self._tasks[album_id] = asyncio.create_task(self._run(album_id, pending))
        return job

    async def _run(self, album_id: str, image_ids: list[str]) -> None:
        try:
            for image_id in image_ids:
                paths = self._store.image_paths(album_id, image_id)
                try:
                    result = await self._classifier.classify(paths.model_input)
                    error = None
                except Exception as exc:
                    log.exception("Klassifizierung fehlgeschlagen: %s", image_id)
                    result, error = None, f"{type(exc).__name__}: {exc}"

                async with self._store.locked(album_id) as album:
                    img = album.find_image(image_id)
                    if img is not None:
                        img.classification = result
                        img.error = error
                        img.status = ImageStatus.ERROR if error else ImageStatus.CLASSIFIED
                    album.job.done += 1
        finally:
            async with self._store.locked(album_id) as album:
                album.job.status = "done"
            self._tasks.pop(album_id, None)
