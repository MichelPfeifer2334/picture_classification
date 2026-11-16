"""Umschlag (Hardcover-Cover): Rückseite + Buchrücken + Vorderseite in einer Datei.

Die Geometrie kommt aus dem Anbieterprofil (services/print_profile.py): Gesamtgröße und
Rückenbreite hängen von der Seitenzahl ab; der Rücken liegt immer mittig.

Das Ergebnis ist eine Liste einfacher Bausteine (Flächen, Bilder, Texte) mit Positionen in mm
– das PDF (services/pdf/cover_pdf.py) und die Browser-Vorschau zeichnen exakt dieselben.

Koordinaten: Ursprung oben links an der Kante der Datei (inkl. Beschnitt), Einheit mm.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from reportlab.pdfbase.pdfmetrics import stringWidth

from app.models.album import Album, ImageRecord, SpineDirection, Style
from app.services.chapters import _MONTHS
from app.services.print_profile import PrintProfile, px
from app.services.styles import polaroid_padding

Font = Literal["sans", "sans-bold", "serif", "serif-italic", "mono", "mono-bold"]

# PDF-Standardschriften je Rolle (auch für die Breitenmessung)
PDF_FONTS: dict[str, str] = {
    "sans": "Helvetica",
    "sans-bold": "Helvetica-Bold",
    "serif": "Times-Roman",
    "serif-italic": "Times-Italic",
    "mono": "Courier",
    "mono-bold": "Courier-Bold",
}
MM_PER_PT = 25.4 / 72


class CoverRect(BaseModel):
    x: float
    y: float
    w: float
    h: float
    color: str  # #rrggbb
    alpha: float = 1.0


class CoverImage(BaseModel):
    image_id: str
    x: float
    y: float
    w: float
    h: float
    focus_x: float = 0.5
    focus_y: float = 0.5
    pad_side: float = 0.0  # Polaroid-Rahmen
    pad_top: float = 0.0
    pad_bottom: float = 0.0
    rotate: float = 0.0  # Grad, positiv = gegen den Uhrzeigersinn
    line_color: str | None = None  # feine Linie um das Bild (elegant)
    tape: bool = False


class CoverText(BaseModel):
    text: str
    x: float  # Textbox
    y: float
    w: float
    h: float
    size: float  # Schriftgröße in mm (Geviert)
    font: Font
    color: str
    align: Literal["left", "center", "right"] = "left"
    spacing: float = 0.0  # zusätzlicher Zeichenabstand in mm
    rotate: Literal[0, 90, -90] = 0  # 90 = von unten nach oben lesbar, -90 = von oben nach unten


class CoverGuides(BaseModel):
    bleed_lr: float
    bleed_tb: float
    spine_x: float
    spine_w: float
    fold: float
    safe: float


class CoverLayout(BaseModel):
    width_mm: float
    height_mm: float
    pages: int
    content_pages: int
    style: Style
    guides: CoverGuides
    background: str
    rects: list[CoverRect]
    images: list[CoverImage]
    texts: list[CoverText]
    # aufgelöste Werte (Automatik → tatsächlich verwendet), für das Formular im Frontend
    title: str
    subtitle: str
    spine_text: str
    spine_direction: SpineDirection
    front_image_id: str | None
    back_image_id: str | None


# --- Farben je Stil -----------------------------------------------------------------


def _palette(paper: str, ink: str, muted: str, spine: str, spine_ink: str) -> dict[str, str]:
    return {"paper": paper, "ink": ink, "muted": muted, "spine": spine, "spine_ink": spine_ink}


PALETTE: dict[Style, dict[str, str]] = {
    "schlicht": _palette("#ffffff", "#29262b", "#85808c", "#ffffff", "#29262b"),
    "elegant": _palette("#f7f2e8", "#29262b", "#a8874a", "#f7f2e8", "#a8874a"),
    "erinnerungen": _palette("#efe7da", "#29262b", "#6f6a63", "#efe7da", "#29262b"),
    "magazin": _palette("#ffffff", "#29262b", "#ff5f6d", "#ff5f6d", "#ffffff"),
}


# --- Automatik ------------------------------------------------------------------------


def date_range(images: list[ImageRecord]) -> str:
    """'August 2026' · 'Juli – August 2026' · 'Dezember 2025 – Januar 2026'."""
    times = sorted(i.taken_at for i in images if i.taken_at)
    if not times:
        return ""
    a, b = times[0], times[-1]
    if (a.year, a.month) == (b.year, b.month):
        return f"{_MONTHS[a.month - 1]} {a.year}"
    if a.year == b.year:
        return f"{_MONTHS[a.month - 1]} – {_MONTHS[b.month - 1]} {a.year}"
    return f"{_MONTHS[a.month - 1]} {a.year} – {_MONTHS[b.month - 1]} {b.year}"


def _year(images: list[ImageRecord]) -> int | None:
    times: list[datetime] = [i.taken_at for i in images if i.taken_at]
    return max(times).year if times else None


def _cover_candidates(album: Album) -> list[ImageRecord]:
    """Ausgewählte Bilder, die gut als Titelbild taugen – bestes zuerst.

    Leicht bevorzugt: annähernd quadratische/quere Bilder (die Vorderseite ist quadratisch)
    und Bilder mit Stärken wie schönem Licht oder einem Wahrzeichen.
    """

    def appeal(img: ImageRecord) -> float:
        bonus = 0.0
        if 0.9 <= img.aspect <= 1.7:
            bonus += 0.3
        if img.classification and {"iconic_place", "golden_hour", "great_light"} & set(
            img.classification.strengths
        ):
            bonus += 0.3
        return (img.rank or 0.0) + bonus

    return sorted((i for i in album.images if i.included), key=appeal, reverse=True)


def resolve(album: Album) -> tuple[str, str, str, str | None, str | None]:
    """(Titel, Untertitel, Rückentext, Vorderbild, Rückbild) – Automatik aufgelöst."""
    c = album.cover
    included = [i for i in album.images if i.included]
    title = c.title if c.title is not None else (album.suggested_title or "Unser Urlaub")
    subtitle = c.subtitle if c.subtitle is not None else date_range(included)
    year = _year(included)
    auto_spine = f"{title.upper()} · {year}" if year else title.upper()
    spine = c.spine_text if c.spine_text is not None else auto_spine

    ids = {i.id for i in album.images}
    candidates = _cover_candidates(album)
    front = c.front_image_id if c.front_image_id in ids else None
    if front is None and candidates:
        front = candidates[0].id
    if c.back_image_id == "":
        back: str | None = None
    elif c.back_image_id in ids:
        back = c.back_image_id
    else:  # automatisch: nächstbestes Bild, möglichst quer
        rest = [i for i in candidates if i.id != front]
        pool = [i for i in rest if i.aspect >= 1.2] or rest
        back = pool[0].id if pool else None
    return title, subtitle, spine, front, back


# --- Text einpassen ------------------------------------------------------------------


def fit_size(text: str, font: Font, size_mm: float, max_w_mm: float, spacing: float = 0.0) -> float:
    """Schriftgröße so weit verkleinern, dass der Text in max_w_mm passt."""
    if not text:
        return size_mm
    pt = size_mm / MM_PER_PT
    width = stringWidth(text, PDF_FONTS[font], pt) * MM_PER_PT + spacing * max(len(text) - 1, 0)
    if width <= max_w_mm:
        return size_mm
    return round(size_mm * max_w_mm / width, 2)


# --- Aufbau ----------------------------------------------------------------------------


def build_cover(album: Album, profile: PrintProfile, content_pages: int) -> CoverLayout:
    spec = profile.cover
    pages = profile.total_pages(content_pages)
    step = spec.step_for(pages)

    W, H = px(step.width_px), px(spec.height_px)
    B, T = px(spec.bleed_lr_px), px(spec.bleed_tb_px)
    spine_w, fold = px(step.spine_px), px(spec.fold_px)
    spine_x = (W - spine_w) / 2
    safe = profile.safe_mm
    style = album.style
    pal = PALETTE[style]

    # Vorderseite: Endformat von Rückenkante bis rechter Endformat-Kante
    front_x0, front_x1 = spine_x + spine_w, W - B
    back_x0, back_x1 = B, spine_x
    # sicherer Bereich (Falz + Abstand bzw. Abstand zur Außenkante)
    fs_x0, fs_x1 = front_x0 + fold + safe, front_x1 - safe
    bs_x0, bs_x1 = back_x0 + safe, back_x1 - fold - safe
    s_y0 = T + safe

    title, subtitle, spine_text, front_id, back_id = resolve(album)
    by_id = {i.id: i for i in album.images}

    rects: list[CoverRect] = []
    images: list[CoverImage] = []
    texts: list[CoverText] = []

    def image(img_id: str | None, x: float, y: float, w: float, h: float, **extra: object) -> None:
        if img_id is None or img_id not in by_id:
            return
        c = by_id[img_id].classification
        images.append(
            CoverImage(
                image_id=img_id,
                x=round(x, 2),
                y=round(y, 2),
                w=round(w, 2),
                h=round(h, 2),
                focus_x=c.focus_x if c else 0.5,
                focus_y=c.focus_y if c else 0.5,
                **extra,
            )
        )

    def text(
        t: str, x: float, y: float, w: float, size: float, font: Font, color: str, **kw: object
    ) -> None:
        if not t:
            return
        spacing = float(kw.get("spacing", 0.0))  # type: ignore[arg-type]
        fitted = fit_size(t, font, size, w, spacing)
        texts.append(
            CoverText(
                text=t,
                x=round(x, 2),
                y=round(y, 2),
                w=round(w, 2),
                h=round(fitted * 1.2, 2),
                size=fitted,
                font=font,
                color=color,
                **kw,
            )
        )

    usable_w = fs_x1 - fs_x0

    # --- Vorderseite je Stil ---
    if style in ("schlicht", "magazin"):
        # Foto randlos über die Vorderseite (ab Ende des Falzes, bis in den Beschnitt)
        image(front_id, front_x0 + fold, 0, W - (front_x0 + fold), H)
        if style == "schlicht":
            band_h = 62.0  # dunkler Verlauf unten für lesbaren Titel
            rects.append(
                CoverRect(
                    x=front_x0 + fold,
                    y=H - band_h - T,
                    w=W - front_x0 - fold,
                    h=band_h + T,
                    color="#000000",
                    alpha=0.32,
                )
            )
            text(title, fs_x0, H - T - safe - 30, usable_w, 15, "sans-bold", "#ffffff")
            text(
                subtitle.upper(),
                fs_x0,
                H - T - safe - 11,
                usable_w,
                4.2,
                "sans",
                "#ffffff",
                spacing=0.6,
            )
        else:
            rects.append(CoverRect(x=fs_x0, y=s_y0, w=2.2, h=24, color=pal["muted"]))
            text(title.upper(), fs_x0 + 6, s_y0 - 1, usable_w - 6, 17, "sans-bold", "#ffffff")
            text(
                subtitle.upper(),
                fs_x0 + 6,
                s_y0 + 17.5,
                usable_w - 6,
                4,
                "sans-bold",
                "#ffffff",
                spacing=1.2,
            )
    elif style == "elegant":
        frame_y0, frame_y1 = s_y0 + 8, H - T - 72
        image(
            front_id,
            fs_x0 + 6,
            frame_y0,
            usable_w - 12,
            frame_y1 - frame_y0,
            line_color=pal["muted"],
        )
        text(title, fs_x0, frame_y1 + 16, usable_w, 13, "serif-italic", pal["ink"], align="center")
        text(
            subtitle.upper(),
            fs_x0,
            frame_y1 + 34,
            usable_w,
            3.6,
            "serif",
            pal["muted"],
            align="center",
            spacing=1.4,
        )
    else:  # erinnerungen – Polaroid, leicht gedreht, mit Klebestreifen
        fw = usable_w * 0.78
        fh = fw * 1.06
        fx = fs_x0 + (usable_w - fw) / 2
        side, top, bottom = polaroid_padding(fw, fh)
        image(
            front_id,
            fx,
            s_y0 + 6,
            fw,
            fh,
            pad_side=round(side * 2, 2),
            pad_top=round(top * 2, 2),
            pad_bottom=round(bottom * 1.6, 2),
            rotate=-2.0,
            tape=True,
        )
        text(title, fs_x0, s_y0 + fh + 20, usable_w, 11, "mono-bold", pal["ink"], align="center")
        text(subtitle, fs_x0, s_y0 + fh + 34, usable_w, 4.2, "mono", pal["muted"], align="center")

    # --- Rückseite: ruhiges Bild, mittig ---
    back_w = bs_x1 - bs_x0
    if style == "erinnerungen":
        bw = back_w * 0.55
        bh = bw * 0.82
        side, top, bottom = polaroid_padding(bw, bh)
        image(
            back_id,
            bs_x0 + (back_w - bw) / 2,
            (H - bh) / 2,
            bw,
            bh,
            pad_side=round(side * 2, 2),
            pad_top=round(top * 2, 2),
            pad_bottom=round(bottom * 1.6, 2),
            rotate=2.5,
            tape=True,
        )
    else:
        bw = back_w * 0.58
        bh = bw * 0.72
        extra = {"line_color": pal["muted"]} if style == "elegant" else {}
        image(back_id, bs_x0 + (back_w - bw) / 2, (H - bh) / 2, bw, bh, **extra)

    # --- Buchrücken: Fläche (etwas breiter wegen Fertigungstoleranz) + gedrehter Titel ---
    if pal["spine"] != pal["paper"]:
        rects.append(CoverRect(x=spine_x - 3, y=0, w=spine_w + 6, h=H, color=pal["spine"]))
    spine_font: Font = {"elegant": "serif-italic", "erinnerungen": "mono-bold"}.get(
        style, "sans-bold"
    )  # type: ignore[assignment]
    spine_len = H - 2 * T - 2 * 22  # oben/unten Abstand zur Kante
    spine_size = fit_size(spine_text, spine_font, spine_w * 0.62, spine_len, 0.8)
    if spine_text:
        texts.append(
            CoverText(
                text=spine_text,
                x=round(spine_x, 2),
                y=round(T + 22, 2),
                w=round(spine_w, 2),
                h=round(spine_len, 2),
                size=spine_size,
                font=spine_font,
                color=pal["spine_ink"],
                align="center",
                spacing=0.8,
                rotate=-90 if album.cover.spine_direction == "top_to_bottom" else 90,
            )
        )

    return CoverLayout(
        width_mm=round(W, 2),
        height_mm=round(H, 2),
        pages=pages,
        content_pages=content_pages,
        style=style,
        guides=CoverGuides(
            bleed_lr=round(B, 2),
            bleed_tb=round(T, 2),
            spine_x=round(spine_x, 2),
            spine_w=round(spine_w, 2),
            fold=round(fold, 2),
            safe=safe,
        ),
        background=pal["paper"],
        rects=rects,
        images=images,
        texts=texts,
        title=title,
        subtitle=subtitle,
        spine_text=spine_text,
        spine_direction=album.cover.spine_direction,
        front_image_id=front_id,
        back_image_id=back_id,
    )
