import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_runner, get_store
from app.core.config import Settings, get_settings
from app.models.album import Album, ImageRecord, JobState, UploadError, UploadResult
from app.services.image_processing import ALLOWED_SUFFIXES, InvalidImageError, process_upload
from app.services.jobs import ClassificationRunner
from app.services.pdf.export import build_pdf
from app.services.storage import AlbumNotFoundError, AlbumStore

router = APIRouter(prefix="/albums", tags=["albums"])

StoreDep = Annotated[AlbumStore, Depends(get_store)]
RunnerDep = Annotated[ClassificationRunner, Depends(get_runner)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _load(store: AlbumStore, album_id: str) -> Album:
    try:
        return store.get(album_id)
    except AlbumNotFoundError as exc:
        raise HTTPException(404, "Album nicht gefunden") from exc


@router.post("", response_model=Album, status_code=201)
def create_album(store: StoreDep) -> Album:
    return store.create()


@router.get("/{album_id}", response_model=Album)
def get_album(album_id: str, store: StoreDep) -> Album:
    return _load(store, album_id)


@router.post("/{album_id}/images", response_model=UploadResult)
async def upload_images(
    album_id: str,
    files: Annotated[list[UploadFile], File(description="Ein oder mehrere Bilder")],
    store: StoreDep,
    runner: RunnerDep,
    settings: SettingsDep,
) -> UploadResult:
    _load(store, album_id)
    if runner.is_running(album_id):
        raise HTTPException(409, "Klassifizierung läuft gerade – bitte warten")

    added: list[ImageRecord] = []
    errors: list[UploadError] = []

    for upload in files:
        name = Path(upload.filename or "unbenannt").name
        if Path(name).suffix.lower() not in ALLOWED_SUFFIXES:
            errors.append(UploadError(filename=name, error="Dateityp nicht unterstützt"))
            continue

        image_id = store.new_id()
        paths = store.image_paths(album_id, image_id)
        data = await upload.read()
        try:
            width, height = await asyncio.to_thread(
                process_upload, data, paths, settings.model_input_max_px, settings.thumb_max_px
            )
        except InvalidImageError as exc:
            errors.append(UploadError(filename=name, error=str(exc)))
            continue
        added.append(ImageRecord(id=image_id, filename=name, width=width, height=height))

    async with store.locked(album_id) as album:
        album.images.extend(added)
        if album.job.status == "done":
            album.job.status = "idle"  # neue Bilder → erneut klassifizierbar

    return UploadResult(added=added, errors=errors)


@router.get("/{album_id}/images/{image_id}/thumb")
def get_thumbnail(album_id: str, image_id: str, store: StoreDep) -> FileResponse:
    try:
        path = store.image_paths(album_id, image_id).thumb
    except AlbumNotFoundError as exc:
        raise HTTPException(404, "Bild nicht gefunden") from exc
    if not path.exists():
        raise HTTPException(404, "Bild nicht gefunden")
    return FileResponse(path, media_type="image/webp")


@router.post("/{album_id}/classify", response_model=JobState)
async def start_classification(album_id: str, store: StoreDep, runner: RunnerDep) -> JobState:
    _load(store, album_id)
    return await runner.start(album_id)


@router.get("/{album_id}/export.pdf")
async def export_pdf(
    album_id: str,
    store: StoreDep,
    runner: RunnerDep,
    settings: SettingsDep,
    exclude_bad: bool = False,
) -> FileResponse:
    album = _load(store, album_id)
    if runner.is_running(album_id):
        raise HTTPException(409, "Klassifizierung läuft noch")
    out = store.export_path(album_id)
    await asyncio.to_thread(build_pdf, album, store, settings.categories, exclude_bad, out)
    return FileResponse(out, media_type="application/pdf", filename="fotobuch.pdf")
