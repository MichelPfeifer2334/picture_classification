"""Bildvorverarbeitung mit Pillow: EXIF-Drehung, Normalisierung, Modell-Input, Thumbnail."""

from io import BytesIO

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from app.services.storage import ImagePaths

register_heif_opener()  # ermöglicht iPhone-HEIC/HEIF

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}


class InvalidImageError(ValueError):
    pass


def process_upload(
    data: bytes, paths: ImagePaths, model_input_max_px: int, thumb_max_px: int
) -> tuple[int, int]:
    """Speichert drei Varianten eines hochgeladenen Bildes und gibt (Breite, Höhe) zurück.

    Synchron/CPU-lastig → aus async-Code per asyncio.to_thread aufrufen.
    """
    try:
        with Image.open(BytesIO(data)) as raw:
            img = ImageOps.exif_transpose(raw).convert("RGB")
    except Exception as exc:  # Pillow wirft je nach Format verschiedene Fehler
        raise InvalidImageError(f"Kein lesbares Bild: {exc}") from exc

    for p in (paths.full, paths.model_input, paths.thumb):
        p.parent.mkdir(parents=True, exist_ok=True)

    img.save(paths.full, "JPEG", quality=92)

    model_img = img.copy()
    model_img.thumbnail((model_input_max_px, model_input_max_px), Image.Resampling.LANCZOS)
    model_img.save(paths.model_input, "JPEG", quality=88)

    thumb = img.copy()
    thumb.thumbnail((thumb_max_px, thumb_max_px), Image.Resampling.LANCZOS)
    thumb.save(paths.thumb, "WEBP", quality=80)

    return img.width, img.height
