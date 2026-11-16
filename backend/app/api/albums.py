import asyncio
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_runner, get_store
from app.core.config import Settings, get_settings
from app.models.album import (
    Album,
    AlbumUpdate,
    BookUpdate,
    Chapter,
    ChapterUpdate,
    CoverUpdate,
    ImageRecord,
    ImageUpdate,
    JobState,
    UploadError,
    UploadResult,
)
from app.services.cover import CoverLayout, build_cover
from app.services.image_processing import ALLOWED_SUFFIXES, InvalidImageError, process_upload
from app.services.jobs import ClassificationRunner
from app.services.layout import BookLayout, build_layout
from app.services.pdf.export import book_sequence, render_cover, render_interior
from app.services.preflight import Preflight, run_preflight
from app.services.print_profile import get_profile
from app.services.selection import curate
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


def _image_file(store: AlbumStore, album_id: str, image_id: str, kind: str) -> Path:
    try:
        paths = store.image_paths(album_id, image_id)
    except AlbumNotFoundError as exc:
        raise HTTPException(404, "Bild nicht gefunden") from exc
    path: Path = getattr(paths, kind)
    if not path.exists():
        raise HTTPException(404, "Bild nicht gefunden")
    return path


# --- Album ----------------------------------------------------------------------


@router.post("", response_model=Album, status_code=201)
def create_album(store: StoreDep, settings: SettingsDep) -> Album:
    album = store.create()
    album.min_score = settings.default_min_score
    store.save(album)
    return album


@router.get("/{album_id}", response_model=Album)
def get_album(album_id: str, store: StoreDep) -> Album:
    return _load(store, album_id)


@router.patch("/{album_id}", response_model=Album)
async def update_album(
    album_id: str, update: AlbumUpdate, store: StoreDep, settings: SettingsDep
) -> Album:
    _load(store, album_id)
    async with store.locked(album_id) as album:
        if update.min_score is not None:
            album.min_score = update.min_score
        if update.style is not None:
            album.style = update.style
        curate(album, settings)
    return album


# --- Bilder ---------------------------------------------------------------------


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
        raise HTTPException(409, "Analyse läuft gerade – bitte warten")

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
            width, height, metrics = await asyncio.to_thread(
                process_upload, data, paths, settings.model_input_max_px, settings.thumb_max_px
            )
        except InvalidImageError as exc:
            errors.append(UploadError(filename=name, error=str(exc)))
            continue
        added.append(
            ImageRecord(id=image_id, filename=name, width=width, height=height, metrics=metrics)
        )

    async with store.locked(album_id) as album:
        album.images.extend(added)
        if album.job.status == "done":
            album.job.status = "idle"  # neue Bilder → erneut analysierbar
        curate(album, settings)
        added = [img for img in album.images if img.id in {a.id for a in added}]

    return UploadResult(added=added, errors=errors)


@router.patch("/{album_id}/images/{image_id}", response_model=Album)
async def update_image(
    album_id: str,
    image_id: str,
    update: ImageUpdate,
    store: StoreDep,
    settings: SettingsDep,
) -> Album:
    """Manuelle Korrektur: aufnehmen/aussortieren (null = Automatik) und Kategorie ändern."""
    _load(store, album_id)
    if update.category is not None and update.category not in settings.categories:
        raise HTTPException(422, f"Unbekannte Kategorie: {update.category}")

    async with store.locked(album_id) as album:
        img = album.find_image(image_id)
        if img is None:
            raise HTTPException(404, "Bild nicht gefunden")
        if "included" in update.model_fields_set:
            img.user_included = update.included
        if update.category is not None and img.classification is not None:
            img.classification.category = update.category
        curate(album, settings)
    return album


@router.get("/{album_id}/images/{image_id}/thumb")
def get_thumbnail(album_id: str, image_id: str, store: StoreDep) -> FileResponse:
    return FileResponse(_image_file(store, album_id, image_id, "thumb"), media_type="image/webp")


@router.get("/{album_id}/images/{image_id}/preview")
def get_preview(album_id: str, image_id: str, store: StoreDep) -> FileResponse:
    """Größere Vorschau (1024 px) für die Lightbox."""
    path = _image_file(store, album_id, image_id, "model_input")
    return FileResponse(path, media_type="image/jpeg")


# --- Analyse ----------------------------------------------------------------------


@router.post("/{album_id}/classify", response_model=JobState)
async def start_classification(
    album_id: str, store: StoreDep, runner: RunnerDep, force: bool = False
) -> JobState:
    """Startet die Analyse. force=true analysiert auch schon bewertete Bilder neu."""
    _load(store, album_id)
    return await runner.start(album_id, force=force)


# --- Fotobuch ---------------------------------------------------------------------


@router.get("/{album_id}/layout", response_model=BookLayout)
def get_layout(album_id: str, store: StoreDep, settings: SettingsDep) -> BookLayout:
    """Seitenaufteilung des Fotobuchs (für Vorschau und Editor)."""
    return build_layout(_load(store, album_id), settings)


@router.put("/{album_id}/book", response_model=BookLayout)
async def save_book(
    album_id: str, update: BookUpdate, store: StoreDep, runner: RunnerDep, settings: SettingsDep
) -> BookLayout:
    """Manuelles Layout aus dem Editor speichern (schaltet in den manuellen Modus)."""
    _load(store, album_id)
    if runner.is_running(album_id):
        raise HTTPException(409, "Analyse läuft noch")
    async with store.locked(album_id) as album:
        known = {img.id for img in album.images}
        seen: set[str] = set()
        for page in update.pages:
            if len(page.image_ids) > 4:
                raise HTTPException(422, "Höchstens 4 Bilder pro Seite")
            for image_id in page.image_ids:
                if image_id not in known or image_id in seen:
                    raise HTTPException(422, f"Ungültiges oder doppeltes Bild: {image_id}")
                seen.add(image_id)
        # Wer ein Bild auf eine Seite legt, will es im Buch haben
        for image_id in [*update.include, *seen]:
            img = album.find_image(image_id)
            if img is not None and not img.included:
                img.user_included = True
        for image_id in update.exclude:
            if img := album.find_image(image_id):
                img.user_included = False
        album.book = [p for p in update.pages if p.image_ids]
        if update.chapters is not None:
            album.book_chapters = [
                Chapter(id=c.id, title=c.title.strip(), title_edited=True) for c in update.chapters
            ]
        elif album.book_chapters is None:
            # Einstieg in den manuellen Modus: automatische Kapitel übernehmen
            album.book_chapters = [c.model_copy() for c in album.chapters]
        curate(album, settings)
    return build_layout(album, settings)


@router.delete("/{album_id}/book", response_model=BookLayout)
async def reset_book(album_id: str, store: StoreDep, settings: SettingsDep) -> BookLayout:
    """Manuelle Änderungen verwerfen → wieder automatisches Layout."""
    _load(store, album_id)
    async with store.locked(album_id) as album:
        album.book = None
        album.book_chapters = None
    return build_layout(album, settings)


@router.patch("/{album_id}/chapters/{chapter_id}", response_model=BookLayout)
async def update_chapter(
    album_id: str,
    chapter_id: str,
    update: ChapterUpdate,
    store: StoreDep,
    settings: SettingsDep,
) -> BookLayout:
    """Kapitelüberschrift ändern (leer = keine Überschrift)."""
    _load(store, album_id)
    async with store.locked(album_id) as album:
        chapter = album.find_chapter(chapter_id)
        if chapter is None:
            raise HTTPException(404, "Kapitel nicht gefunden")
        chapter.title = update.title.strip()
        chapter.title_edited = True
    return build_layout(album, settings)


# --- Umschlag, Preflight, Export ----------------------------------------------------


def _cover(album: Album, settings: Settings) -> CoverLayout:
    profile = get_profile(settings.print_profile)
    _, info = book_sequence(build_layout(album, settings), profile)
    return build_cover(album, profile, info.content_pages)


@router.get("/{album_id}/cover", response_model=CoverLayout)
def get_cover(album_id: str, store: StoreDep, settings: SettingsDep) -> CoverLayout:
    """Umschlag-Layout (Rückseite · Rücken · Vorderseite) für Vorschau und Formular."""
    return _cover(_load(store, album_id), settings)


@router.patch("/{album_id}/cover", response_model=CoverLayout)
async def update_cover(
    album_id: str, update: CoverUpdate, store: StoreDep, settings: SettingsDep
) -> CoverLayout:
    """Titel, Untertitel, Rückentext, Bilder, Schreibrichtung. `null` = wieder automatisch."""
    _load(store, album_id)
    async with store.locked(album_id) as album:
        ids = {img.id for img in album.images}
        for key in update.model_fields_set:
            value = getattr(update, key)
            if key == "front_image_id" and value not in (None, *ids):
                raise HTTPException(422, "Unbekanntes Titelbild")
            if key == "back_image_id" and value not in (None, "", *ids):
                raise HTTPException(422, "Unbekanntes Rückseitenbild")
            if key == "spine_direction" and value is None:
                continue
            setattr(album.cover, key, value.strip() if isinstance(value, str) else value)
    return _cover(album, settings)


@router.get("/{album_id}/preflight", response_model=Preflight)
def preflight(album_id: str, store: StoreDep, settings: SettingsDep) -> Preflight:
    """Prüfung gegen die Vorgaben des Anbieters (Seitenzahl, Auflösung, Umschlag)."""
    return run_preflight(_load(store, album_id), settings, get_profile(settings.print_profile))


async def _export(
    album_id: str, kind: str, store: AlbumStore, runner: ClassificationRunner, settings: Settings
) -> FileResponse:
    album = _load(store, album_id)
    if runner.is_running(album_id):
        raise HTTPException(409, "Analyse läuft noch")
    profile = get_profile(settings.print_profile)
    out = store.export_path(album_id).with_name(f"{kind}.pdf")
    if kind == "innenteil":
        layout = build_layout(album, settings)
        await asyncio.to_thread(render_interior, layout, album, store, settings, profile, out)
    else:
        cover = _cover(album, settings)
        await asyncio.to_thread(render_cover, cover, album, store, settings, out)
    return FileResponse(out, media_type="application/pdf", filename=f"fotobuch-{kind}.pdf")


@router.get("/{album_id}/export/innenteil.pdf")
async def export_interior(
    album_id: str, store: StoreDep, runner: RunnerDep, settings: SettingsDep
) -> FileResponse:
    """Innenteil für den Anbieter (bei Saal: Doppelseiten, eine PDF-Seite pro Doppelseite)."""
    return await _export(album_id, "innenteil", store, runner, settings)


@router.get("/{album_id}/export/umschlag.pdf")
async def export_cover(
    album_id: str, store: StoreDep, runner: RunnerDep, settings: SettingsDep
) -> FileResponse:
    """Umschlag als eine Datei: Rückseite · Rücken · Vorderseite inkl. Beschnitt."""
    return await _export(album_id, "umschlag", store, runner, settings)


@router.get("/{album_id}/export.pdf")
async def export_pdf(
    album_id: str, store: StoreDep, runner: RunnerDep, settings: SettingsDep
) -> FileResponse:
    """Kompatibilität: liefert den Innenteil."""
    return await _export(album_id, "innenteil", store, runner, settings)
