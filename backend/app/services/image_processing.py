"""Bildvorverarbeitung mit Pillow: EXIF, Normalisierung, Modell-Input, Thumbnail, Messwerte."""

from datetime import datetime
from io import BytesIO
from pathlib import Path

import imagehash
import numpy as np
from PIL import ExifTags, Image, ImageOps
from pillow_heif import register_heif_opener

from app.models.album import ImageMetrics
from app.services.storage import ImagePaths

register_heif_opener()  # ermöglicht iPhone-HEIC/HEIF

ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp"}


class InvalidImageError(ValueError):
    pass


def _taken_at(raw: Image.Image) -> datetime | None:
    """Aufnahmezeit aus EXIF (DateTimeOriginal, sonst DateTime)."""
    try:
        exif = raw.getexif()
        value = exif.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.DateTimeOriginal) or exif.get(
            ExifTags.Base.DateTime
        )
        if not value:
            return None
        return datetime.strptime(str(value).strip("\x00 "), "%Y:%m:%d %H:%M:%S")
    except Exception:
        return None


def _sharpness(gray: np.ndarray) -> float:
    """Laplace-Varianz pro Kachel (4×4), davon das 90. Perzentil.

    Kacheln statt Gesamtbild, damit Fotos mit unscharfem Hintergrund (Bokeh) oder viel
    Himmel nicht fälschlich als unscharf gelten – entscheidend ist der schärfste Bereich.
    """
    g = gray.astype(np.float32)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    h, w = lap.shape
    th, tw = max(h // 4, 1), max(w // 4, 1)
    tiles = [
        float(lap[i * th : (i + 1) * th, j * tw : (j + 1) * tw].var())
        for i in range(4)
        for j in range(4)
    ]
    return float(np.percentile(tiles, 90))


def compute_metrics(img: Image.Image, taken_at: datetime | None = None) -> ImageMetrics:
    """Messwerte auf einem (verkleinerten) RGB-Bild – Skala ~1024 px für vergleichbare Werte."""
    gray = np.asarray(img.convert("L"))
    return ImageMetrics(
        sharpness=round(_sharpness(gray), 2),
        brightness=round(float(gray.mean()), 2),
        dark_fraction=round(float((gray < 16).mean()), 4),
        bright_fraction=round(float((gray > 240).mean()), 4),
        phash=str(imagehash.phash(img)),
        taken_at=taken_at,
    )


def metrics_from_file(path: Path) -> ImageMetrics:
    """Nachberechnung für Bilder, die vor Einführung der Messwerte hochgeladen wurden."""
    with Image.open(path) as img:
        return compute_metrics(img.convert("RGB"))


def process_upload(
    data: bytes, paths: ImagePaths, model_input_max_px: int, thumb_max_px: int
) -> tuple[int, int, ImageMetrics]:
    """Speichert drei Varianten eines Bildes und gibt (Breite, Höhe, Messwerte) zurück.

    Synchron/CPU-lastig → aus async-Code per asyncio.to_thread aufrufen.
    """
    try:
        with Image.open(BytesIO(data)) as raw:
            taken_at = _taken_at(raw)
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
    thumb.save(paths.thumb, "WEBP", quality=82)

    return img.width, img.height, compute_metrics(model_img, taken_at)
