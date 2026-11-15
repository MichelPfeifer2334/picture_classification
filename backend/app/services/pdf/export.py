"""Fotobuch-PDF: rendert das Layout aus services/layout.py.

- Seitengröße = Endformat + Beschnittzugabe ringsum (für den Druck)
- Jedes Bild wird auf das Seitenverhältnis seiner Zelle zugeschnitten – um den vom Modell
  gemeldeten Bildschwerpunkt (z. B. Gesichter) herum – und auf print_dpi heruntergerechnet
- Text nur als kurze Kapitelüberschrift (+ Datum) auf der ersten Seite eines Kapitels
"""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps
from reportlab.lib.colors import Color
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.core.config import Settings
from app.models.album import Album
from app.services.layout import BookLayout, Cell, Page, build_layout
from app.services.storage import AlbumStore

TITLE_FONT = "Helvetica-Bold"
SUBTITLE_FONT = "Helvetica"
DARK = Color(0.16, 0.15, 0.17)
GREY = Color(0.52, 0.5, 0.55)


def _render_cell(path: Path, cell: Cell, dpi: int) -> ImageReader:
    target = (max(1, round(cell.w / 25.4 * dpi)), max(1, round(cell.h / 25.4 * dpi)))
    with Image.open(path) as img:
        fitted = ImageOps.fit(
            img.convert("RGB"),
            target,
            Image.Resampling.LANCZOS,
            centering=(cell.focus_x, cell.focus_y),
        )
    buf = BytesIO()
    fitted.save(buf, "JPEG", quality=90)
    buf.seek(0)
    return ImageReader(buf)


def _draw_title(pdf: canvas.Canvas, page: Page, layout: BookLayout, page_h: float) -> None:
    if not page.title:
        return
    b = layout.bleed_mm
    x = (layout.margin_mm + b) * mm
    top = page_h - (layout.margin_mm + b)  # mm, von unten gemessen
    on_photo = page.template == "full_bleed"
    pdf.setFillColor(Color(1, 1, 1) if on_photo else DARK)
    pdf.setFont(TITLE_FONT, 17)
    pdf.drawString(x, (top - 7) * mm, page.title)
    if page.subtitle:
        pdf.setFillColor(Color(1, 1, 1, alpha=0.85) if on_photo else GREY)
        pdf.setFont(SUBTITLE_FONT, 8.5)
        pdf.drawString(x, (top - 12) * mm, page.subtitle.upper())


def render_pdf(layout: BookLayout, album: Album, store: AlbumStore, s: Settings, out: Path) -> int:
    out.parent.mkdir(parents=True, exist_ok=True)
    b = layout.bleed_mm
    page_w = layout.page_width_mm + 2 * b
    page_h = layout.page_height_mm + 2 * b

    pdf = canvas.Canvas(str(out), pagesize=(page_w * mm, page_h * mm))
    pdf.setTitle("Fotobuch")

    if not layout.pages:
        pdf.showPage()  # leere Seite statt kaputter Datei

    for page in layout.pages:
        for cell in page.cells:
            path = store.image_paths(album.id, cell.image_id).full
            reader = _render_cell(path, cell, s.print_dpi)
            # Layout-Koordinaten: oben links, ohne Beschnitt → PDF: unten links, mit Beschnitt
            x = (cell.x + b) * mm
            y = (page_h - (cell.y + b) - cell.h) * mm
            pdf.drawImage(reader, x, y, width=cell.w * mm, height=cell.h * mm)
        _draw_title(pdf, page, layout, page_h)
        pdf.showPage()

    pdf.save()
    return max(1, len(layout.pages))


def build_pdf(album: Album, store: AlbumStore, s: Settings, out: Path) -> int:
    """Layout berechnen und PDF schreiben. Gibt die Seitenzahl zurück."""
    return render_pdf(build_layout(album, s), album, store, s, out)
