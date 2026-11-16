"""Preflight: prüft das Fotobuch gegen die Vorgaben des Anbieters, bevor hochgeladen wird.

- Seitenzahl im erlaubten Bereich? Wie viele leere Seiten werden aufgefüllt?
- Druckauflösung jedes Bildes in seinem Feld (empfohlen 300 dpi)
- Umschlag: Titelbild vorhanden, Rückentext passt auf den Rücken
- Ausgewählte, aber nicht platzierte Bilder (manuelles Layout)
"""

from typing import Literal

from pydantic import BaseModel

from app.core.config import Settings
from app.models.album import Album
from app.services.cover import build_cover
from app.services.layout import build_layout
from app.services.pdf.export import book_sequence
from app.services.print_profile import PrintProfile

DPI_WARN = 200
DPI_ERROR = 120
MIN_SPINE_TEXT_MM = 3.0


class PreflightIssue(BaseModel):
    level: Literal["error", "warning", "info"]
    text: str
    page: int | None = None  # Buchseite (1-basiert, inkl. Vorsatz)
    image_id: str | None = None


class Preflight(BaseModel):
    profile: str
    total_pages: int
    content_pages: int
    blank_pages: int
    max_content_pages: int
    spine_mm: float
    ok: bool
    issues: list[PreflightIssue]


def effective_dpi(img_w_px: int, img_h_px: int, w_mm: float, h_mm: float) -> float:
    """Auflösung im Druck, wenn das Bild sein Feld vollständig füllt (Zuschnitt wie im PDF)."""
    mm_per_px = max(w_mm / img_w_px, h_mm / img_h_px)
    return 25.4 / mm_per_px


def run_preflight(album: Album, s: Settings, profile: PrintProfile) -> Preflight:
    layout = build_layout(album, s)
    seq, info = book_sequence(layout, profile)
    cover = build_cover(album, profile, info.content_pages)
    by_id = {img.id: img for img in album.images}
    issues: list[PreflightIssue] = []

    if info.content_pages == 0:
        issues.append(PreflightIssue(level="error", text="Das Buch hat noch keine Fotoseiten."))
    if info.content_pages > profile.max_content_pages:
        issues.append(
            PreflightIssue(
                level="error",
                text=(
                    f"Das Buch hat {info.content_pages} Fotoseiten, {profile.name} erlaubt "
                    f"höchstens {profile.max_content_pages} (plus 2 weiße Vorsatzseiten). "
                    "Strenge erhöhen, "
                    "Bilder entfernen oder im Editor mehr Bilder pro Seite setzen."
                ),
            )
        )
    if info.blank_pages:
        issues.append(
            PreflightIssue(
                level="info",
                text=(
                    f"{info.blank_pages} leere Seite(n) am Ende – das Buch muss mindestens "
                    f"{profile.min_pages} Seiten haben (in {profile.page_step}er-Schritten). "
                    "Mit mehr Bildern im Buch werden sie gefüllt."
                ),
            )
        )
    if layout.unplaced:
        issues.append(
            PreflightIssue(
                level="warning",
                text=(
                    f"{len(layout.unplaced)} ausgewählte Bilder stehen auf keiner Seite "
                    "und werden nicht gedruckt."
                ),
            )
        )

    for number, page in enumerate(seq, start=1):
        if page is None:
            continue
        for cell in page.cells:
            img = by_id.get(cell.image_id)
            if img is None:
                continue
            w = cell.w - 2 * cell.pad_side
            h = cell.h - cell.pad_top - cell.pad_bottom
            dpi = effective_dpi(img.width, img.height, w, h)
            if dpi < DPI_WARN:
                issues.append(
                    PreflightIssue(
                        level="error" if dpi < DPI_ERROR else "warning",
                        text=(
                            f"Seite {number}: {img.filename} wird mit nur {dpi:.0f} dpi "
                            "gedruckt (empfohlen 300) – kleineres Feld wählen."
                        ),
                        page=number,
                        image_id=img.id,
                    )
                )

    if cover.front_image_id is None:
        issues.append(PreflightIssue(level="error", text="Umschlag: kein Titelbild vorhanden."))
    for img_c in cover.images:
        img = by_id.get(img_c.image_id)
        if img is None:
            continue
        dpi = effective_dpi(
            img.width,
            img.height,
            img_c.w - 2 * img_c.pad_side,
            img_c.h - img_c.pad_top - img_c.pad_bottom,
        )
        if dpi < DPI_WARN:
            issues.append(
                PreflightIssue(
                    level="error" if dpi < DPI_ERROR else "warning",
                    text=(
                        f"Umschlag: {img.filename} wird mit nur {dpi:.0f} dpi gedruckt "
                        "(empfohlen 300)."
                    ),
                    image_id=img.id,
                )
            )
    spine = next((t for t in cover.texts if t.rotate), None)
    if spine is not None and spine.size < MIN_SPINE_TEXT_MM:
        issues.append(
            PreflightIssue(
                level="warning",
                text="Umschlag: Der Rückentext ist sehr lang und wird winzig – kürzer fassen.",
            )
        )

    return Preflight(
        profile=profile.name,
        total_pages=info.total_pages,
        content_pages=info.content_pages,
        blank_pages=info.blank_pages,
        max_content_pages=profile.max_content_pages,
        spine_mm=cover.guides.spine_w,
        ok=not any(i.level == "error" for i in issues),
        issues=issues,
    )
