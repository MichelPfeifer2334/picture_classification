"""Druck-PDFs: Innenteil (services/layout.py) und Umschlag (services/cover.py).

Innenteil
- je nach Anbieterprofil Einzelseiten oder **Doppelseiten** (eine PDF-Seite = zwei Buchseiten)
- Beschnitt nur an den Außenkanten; am Bund stoßen die Seiten direkt aneinander –
  jede Seitenhälfte wird beschnitten, damit randlose Bilder nicht auf die Nachbarseite ragen
- erste und letzte Seite bleiben weiß, wenn sie auf die Buchdeckel geklebt werden
- aufgefüllt auf die nächste erlaubte Seitenzahl
- Bilder um den Bildschwerpunkt auf ihr Feld zugeschnitten und auf print_dpi heruntergerechnet
- Stil (services/styles.py): Papierfarbe, Rahmen, Überschriften

Nur PDF-Standardschriften (Helvetica, Times, Courier) – keine Schriftdateien nötig.
"""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps
from reportlab.lib.colors import Color, HexColor
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.core.config import Settings
from app.models.album import Album
from app.services.cover import PDF_FONTS, CoverLayout
from app.services.layout import BookLayout, Cell, Page, build_layout
from app.services.print_profile import PrintProfile, get_profile
from app.services.storage import AlbumStore
from app.services.styles import STYLES

INK = Color(0.16, 0.15, 0.17)
GREY = Color(0.52, 0.5, 0.55)
GOLD = Color(0.66, 0.53, 0.29)
ACCENT = Color(1.0, 0.37, 0.43)  # Sonnenuntergangs-Rot aus dem App-Design
WHITE = Color(1, 1, 1)


def _image(path: Path, w_mm: float, h_mm: float, fx: float, fy: float, dpi: int) -> ImageReader:
    target = (max(1, round(w_mm / 25.4 * dpi)), max(1, round(h_mm / 25.4 * dpi)))
    with Image.open(path) as img:
        fitted = ImageOps.fit(
            img.convert("RGB"), target, Image.Resampling.LANCZOS, centering=(fx, fy)
        )
    buf = BytesIO()
    fitted.save(buf, "JPEG", quality=90)
    buf.seek(0)
    return ImageReader(buf)


@dataclass(frozen=True)
class InteriorInfo:
    total_pages: int  # Buchseiten laut Anbieter (inkl. weißer Vorsatzseiten)
    content_pages: int  # Seiten mit Fotos
    blank_pages: int  # zum Auffüllen eingefügte leere Seiten
    sheets: int  # Seiten im PDF


# --- Innenteil -----------------------------------------------------------------------


class _PageRenderer:
    """Zeichnet eine Buchseite an einer Position innerhalb eines PDF-Blatts."""

    def __init__(
        self,
        pdf: canvas.Canvas,
        layout: BookLayout,
        s: Settings,
        sheet_h: float,
        album: Album,
        store: AlbumStore,
    ) -> None:
        self.pdf = pdf
        self.album = album
        self.store = store
        self.layout = layout
        self.s = s
        self.style = STYLES[layout.style]
        self.b = layout.bleed_mm
        self.sheet_h = sheet_h  # mm
        self.ox = self.b  # mm: x der linken Endformat-Kante dieser Seite im Blatt

    def _x(self, x_mm: float) -> float:
        return (x_mm + self.ox) * mm

    def _y(self, y_mm: float, h_mm: float) -> float:
        return (self.sheet_h - (y_mm + self.b) - h_mm) * mm

    def draw(self, page: Page | None, ox: float, clip: tuple[float, float]) -> None:
        """Seite (oder leere Seite) zeichnen; clip = (x0, x1) in mm im Blatt."""
        self.ox = ox
        pdf = self.pdf
        pdf.saveState()
        path = pdf.beginPath()
        path.rect(clip[0] * mm, 0, (clip[1] - clip[0]) * mm, self.sheet_h * mm)
        pdf.clipPath(path, stroke=0, fill=0)
        r, g, b = self.style.background
        if (r, g, b) != (1.0, 1.0, 1.0):
            pdf.setFillColor(Color(r, g, b))
            pdf.rect(clip[0] * mm, 0, (clip[1] - clip[0]) * mm, self.sheet_h * mm, fill=1, stroke=0)
        if page is not None:
            for cell in page.cells:
                path_img = self.store.image_paths(self.album.id, cell.image_id).full
                self.cell(cell, path_img, page.template)
            self.title(page)
        pdf.restoreState()

    def cell(self, cell: Cell, path: Path, template: str) -> None:
        pdf = self.pdf
        if self.style.polaroid and template != "full_bleed":
            self._polaroid(cell, path)
            return
        reader = _image(path, cell.w, cell.h, cell.focus_x, cell.focus_y, self.s.print_dpi)
        x, y = self._x(cell.x), self._y(cell.y, cell.h)
        pdf.drawImage(reader, x, y, width=cell.w * mm, height=cell.h * mm)
        if self.style.frame_line and template != "full_bleed":
            off = 1.4 * mm
            pdf.setStrokeColor(Color(*self.style.frame_line))
            pdf.setLineWidth(0.5)
            pdf.rect(
                x - off, y - off, cell.w * mm + 2 * off, cell.h * mm + 2 * off, fill=0, stroke=1
            )

    def _polaroid(self, cell: Cell, path: Path) -> None:
        _draw_polaroid(
            self.pdf,
            path,
            self.s.print_dpi,
            cx=self._x(cell.x) + cell.w * mm / 2,
            cy=self._y(cell.y, cell.h) + cell.h * mm / 2,
            w=cell.w,
            h=cell.h,
            pad=(cell.pad_side, cell.pad_top, cell.pad_bottom),
            rotate=cell.rotate,
            focus=(cell.focus_x, cell.focus_y),
            tape=True,
        )

    def title(self, page: Page) -> None:
        if not page.title:
            return
        pdf = self.pdf
        layout = self.layout
        on_photo = page.template == "full_bleed"
        top = layout.margin_mm
        left = self._x(layout.margin_mm)

        def baseline(offset_mm: float) -> float:
            return (self.sheet_h - self.b - top - offset_mm) * mm

        match layout.style:
            case "elegant":
                centre = self._x(layout.page_width_mm / 2)
                pdf.setFillColor(WHITE if on_photo else INK)
                pdf.setFont("Times-Italic", 22)
                pdf.drawCentredString(centre, baseline(8), page.title)
                if page.subtitle:
                    pdf.setFillColor(WHITE if on_photo else GOLD)
                    pdf.setFont("Times-Roman", 8.5)
                    pdf.drawCentredString(
                        centre, baseline(13.2), page.subtitle.upper(), charSpace=1.4
                    )
            case "erinnerungen":
                pdf.setFillColor(WHITE if on_photo else INK)
                pdf.setFont("Courier-Bold", 17)
                pdf.drawString(left, baseline(7.5), page.title)
                if page.subtitle:
                    pdf.setFillColor(WHITE if on_photo else GREY)
                    pdf.setFont("Courier", 9)
                    pdf.drawString(left, baseline(12.5), page.subtitle)
            case "magazin":
                pdf.setFillColor(ACCENT)
                pdf.rect(left, baseline(12.8), 1.6 * mm, 12.6 * mm, fill=1, stroke=0)
                x = left + 4.5 * mm
                pdf.setFillColor(WHITE if on_photo else INK)
                pdf.setFont("Helvetica-Bold", 21)
                pdf.drawString(x, baseline(7.8), page.title.upper())
                if page.subtitle:
                    pdf.setFillColor(WHITE if on_photo else ACCENT)
                    pdf.setFont("Helvetica-Bold", 7.5)
                    pdf.drawString(x, baseline(12.6), page.subtitle.upper(), charSpace=0.8)
            case _:  # schlicht
                pdf.setFillColor(WHITE if on_photo else INK)
                pdf.setFont("Helvetica-Bold", 17)
                pdf.drawString(left, baseline(7), page.title)
                if page.subtitle:
                    pdf.setFillColor(Color(1, 1, 1, alpha=0.85) if on_photo else GREY)
                    pdf.setFont("Helvetica", 8.5)
                    pdf.drawString(left, baseline(12), page.subtitle.upper())


def book_sequence(
    layout: BookLayout, profile: PrintProfile
) -> tuple[list[Page | None], InteriorInfo]:
    """Buchseiten in Druckreihenfolge: None = leere Seite (Vorsatz oder Auffüllung)."""
    content = list(layout.pages)
    endpapers = 2 if profile.blank_endpapers else 0
    total = profile.total_pages(len(content))
    total = max(total, len(content) + endpapers)
    if total % 2:
        total += 1
    blanks = total - len(content) - endpapers
    seq: list[Page | None] = []
    if profile.blank_endpapers:
        seq.append(None)
    seq.extend(content)
    seq.extend([None] * blanks)
    if profile.blank_endpapers:
        seq.append(None)
    sheets = total // 2 if profile.spreads else total
    return seq, InteriorInfo(total, len(content), blanks, sheets)


def render_interior(
    layout: BookLayout,
    album: Album,
    store: AlbumStore,
    s: Settings,
    profile: PrintProfile,
    out: Path,
) -> InteriorInfo:
    out.parent.mkdir(parents=True, exist_ok=True)
    seq, info = book_sequence(layout, profile)
    b, pw, ph = layout.bleed_mm, layout.page_width_mm, layout.page_height_mm
    sheet_h = ph + 2 * b
    sheet_w = (2 * pw if profile.spreads else pw) + 2 * b

    pdf = canvas.Canvas(str(out), pagesize=(sheet_w * mm, sheet_h * mm))
    pdf.setTitle("Fotobuch – Innenteil")
    renderer = _PageRenderer(pdf, layout, s, sheet_h, album, store)

    if profile.spreads:
        for i in range(0, len(seq), 2):
            # linke Seite: Beschnitt links, endet am Bund · rechte Seite: beginnt am Bund
            renderer.draw(seq[i], ox=b, clip=(0, b + pw))
            renderer.draw(seq[i + 1], ox=b + pw, clip=(b + pw, sheet_w))
            pdf.showPage()
    else:
        for page in seq:
            renderer.draw(page, ox=b, clip=(0, sheet_w))
            pdf.showPage()

    pdf.save()
    return info


# --- Umschlag ------------------------------------------------------------------------


def _draw_polaroid(
    pdf: canvas.Canvas,
    path: Path,
    dpi: int,
    *,
    cx: float,
    cy: float,
    w: float,
    h: float,
    pad: tuple[float, float, float],
    rotate: float,
    focus: tuple[float, float],
    tape: bool,
) -> None:
    """Weißer Sofortbild-Rahmen um (cx, cy) in Punkten, Größe in mm, mit Schatten und Klebeband."""
    side, top, bottom = pad
    iw, ih = w - 2 * side, h - top - bottom
    reader = _image(path, iw, ih, focus[0], focus[1], dpi)
    W, H = w * mm, h * mm
    pdf.saveState()
    pdf.translate(cx, cy)
    pdf.rotate(rotate)
    pdf.setFillColor(Color(0, 0, 0, alpha=0.16))
    pdf.rect(-W / 2 + 0.7 * mm, -H / 2 - 0.9 * mm, W, H, fill=1, stroke=0)
    pdf.setFillColor(WHITE)
    pdf.rect(-W / 2, -H / 2, W, H, fill=1, stroke=0)
    pdf.drawImage(reader, -W / 2 + side * mm, -H / 2 + bottom * mm, width=iw * mm, height=ih * mm)
    if tape:
        tape_w, tape_h = min(22.0, w * 0.3) * mm, 6.5 * mm
        pdf.translate(0, H / 2)
        pdf.rotate(-rotate * 2.5 + 3)
        pdf.setFillColor(Color(0.96, 0.86, 0.62, alpha=0.72))
        pdf.rect(-tape_w / 2, -tape_h / 2, tape_w, tape_h, fill=1, stroke=0)
    pdf.restoreState()


def _color(hex_: str, alpha: float = 1.0) -> Color:
    c = HexColor(hex_)
    return Color(c.red, c.green, c.blue, alpha=alpha)


def render_cover(
    cover: CoverLayout, album: Album, store: AlbumStore, s: Settings, out: Path
) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    W, H = cover.width_mm, cover.height_mm
    pdf = canvas.Canvas(str(out), pagesize=(W * mm, H * mm))
    pdf.setTitle("Fotobuch – Umschlag")

    def y(top_mm: float, h_mm: float) -> float:
        return (H - top_mm - h_mm) * mm

    pdf.setFillColor(_color(cover.background))
    pdf.rect(0, 0, W * mm, H * mm, fill=1, stroke=0)

    for img in cover.images:
        path = store.image_paths(album.id, img.image_id).full
        if img.pad_side or img.pad_bottom:
            _draw_polaroid(
                pdf,
                path,
                s.print_dpi,
                cx=(img.x + img.w / 2) * mm,
                cy=y(img.y, img.h) + img.h * mm / 2,
                w=img.w,
                h=img.h,
                pad=(img.pad_side, img.pad_top, img.pad_bottom),
                rotate=img.rotate,
                focus=(img.focus_x, img.focus_y),
                tape=img.tape,
            )
            continue
        reader = _image(path, img.w, img.h, img.focus_x, img.focus_y, s.print_dpi)
        pdf.drawImage(reader, img.x * mm, y(img.y, img.h), width=img.w * mm, height=img.h * mm)
        if img.line_color:
            off = 2 * mm
            pdf.setStrokeColor(_color(img.line_color))
            pdf.setLineWidth(0.6)
            pdf.rect(
                img.x * mm - off,
                y(img.y, img.h) - off,
                img.w * mm + 2 * off,
                img.h * mm + 2 * off,
                fill=0,
                stroke=1,
            )

    for rect in cover.rects:  # Flächen nach den Bildern (z. B. Verlauf über dem Foto)
        pdf.setFillColor(_color(rect.color, rect.alpha))
        pdf.rect(rect.x * mm, y(rect.y, rect.h), rect.w * mm, rect.h * mm, fill=1, stroke=0)

    for t in cover.texts:
        size_pt = t.size / 25.4 * 72
        pdf.setFillColor(_color(t.color))
        pdf.setFont(PDF_FONTS[t.font], size_pt)
        space = t.spacing * mm
        if t.rotate:
            pdf.saveState()
            pdf.translate((t.x + t.w / 2) * mm, y(t.y, t.h) + t.h * mm / 2)
            pdf.rotate(t.rotate)
            pdf.drawCentredString(0, -size_pt * 0.35, t.text, charSpace=space)
            pdf.restoreState()
            continue
        base = y(t.y, 0) - size_pt * 0.8  # Grundlinie unter der Oberkante der Box
        if t.align == "center":
            pdf.drawCentredString((t.x + t.w / 2) * mm, base, t.text, charSpace=space)
        elif t.align == "right":
            pdf.drawRightString((t.x + t.w) * mm, base, t.text, charSpace=space)
        else:
            pdf.drawString(t.x * mm, base, t.text, charSpace=space)

    pdf.showPage()
    pdf.save()


# --- Einstieg -------------------------------------------------------------------------


def build_pdf(album: Album, store: AlbumStore, s: Settings, out: Path) -> int:
    """Innenteil berechnen und schreiben. Gibt die Anzahl Buchseiten zurück."""
    info = render_interior(
        build_layout(album, s), album, store, s, get_profile(s.print_profile), out
    )
    return info.total_pages
