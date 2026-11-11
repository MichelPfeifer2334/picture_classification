"""Schlichter PDF-Export (MVP): A4 hoch, ein Bild pro Seite, darunter Kategorie + Bildunterschrift.

Bilder sind nach Kategorie (Reihenfolge wie in der Konfiguration) und dann Dateiname sortiert.
"""

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.models.album import Album, ImageRecord, ImageStatus
from app.services.storage import AlbumStore

MARGIN = 15 * mm
TEXT_AREA = 18 * mm
UNCLASSIFIED = "unklassifiziert"


def select_images(album: Album, categories: list[str], exclude_bad: bool) -> list[ImageRecord]:
    def category_of(img: ImageRecord) -> str:
        return img.classification.category if img.classification else UNCLASSIFIED

    order = {cat: i for i, cat in enumerate(categories)}
    images = [
        img
        for img in album.images
        if not (exclude_bad and img.classification and img.classification.quality == "bad")
    ]
    return sorted(images, key=lambda img: (order.get(category_of(img), len(order)), img.filename))


def build_pdf(
    album: Album, store: AlbumStore, categories: list[str], exclude_bad: bool, out: Path
) -> int:
    """Schreibt das PDF nach `out` und gibt die Anzahl der Seiten zurück."""
    images = select_images(album, categories, exclude_bad)
    out.parent.mkdir(parents=True, exist_ok=True)

    page_w, page_h = A4
    box_w = page_w - 2 * MARGIN
    box_h = page_h - 2 * MARGIN - TEXT_AREA

    pdf = canvas.Canvas(str(out), pagesize=A4)
    pdf.setTitle("Fotobuch")

    if not images:
        pdf.setFont("Helvetica", 14)
        pdf.drawCentredString(page_w / 2, page_h / 2, "Keine Bilder ausgewählt.")
        pdf.showPage()
        pdf.save()
        return 1

    for img in images:
        path = store.image_paths(album.id, img.id).full
        reader = ImageReader(str(path))
        iw, ih = reader.getSize()
        scale = min(box_w / iw, box_h / ih)
        w, h = iw * scale, ih * scale
        x = (page_w - w) / 2
        y = MARGIN + TEXT_AREA + (box_h - h) / 2
        pdf.drawImage(reader, x, y, width=w, height=h)

        if img.status == ImageStatus.CLASSIFIED and img.classification:
            label = f"{img.classification.category.capitalize()} · {img.classification.caption}"
        else:
            label = f"{UNCLASSIFIED.capitalize()} · {img.filename}"
        pdf.setFont("Helvetica", 11)
        pdf.drawCentredString(page_w / 2, MARGIN + TEXT_AREA / 2, label)
        pdf.showPage()

    pdf.save()
    return len(images)
