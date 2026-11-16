"""Gestaltungsstile des Fotobuchs.

Ein Stil verändert nur die Optik – nie die Bildauswahl oder die Seitenaufteilung.
Text bleibt in allen Stilen gleich knapp: Kapitelüberschrift + Datum.

- schlicht:     weiß · Bilder randlos im Raster · Helvetica fett, links
- elegant:      creme · feine Goldlinie um jedes Bild · Times kursiv, zentriert, Datum in Gold
- erinnerungen: Papierton · Polaroid-Rahmen, leicht gedreht, Klebestreifen · Schreibmaschine
- magazin:      weiß · Bilder randlos · große Versalien mit Farbbalken, Datum in Akzentfarbe

Geometrie-Anteile (Rahmen-Innenabstand, Drehung) werden hier berechnet und im Layout
mitgeliefert, damit Vorschau (CSS) und PDF (ReportLab) exakt übereinstimmen.
"""

import hashlib
from dataclasses import dataclass

from app.models.album import Style


@dataclass(frozen=True)
class StyleSpec:
    background: tuple[float, float, float]  # RGB 0–1, ganze Seite inkl. Beschnitt
    polaroid: bool = False  # weißer Rahmen, unten breiter, leicht gedreht, Klebeband
    frame_line: tuple[float, float, float] | None = None  # feine Linie um das Bild
    title_align: str = "left"  # "left" | "center"


STYLES: dict[Style, StyleSpec] = {
    "schlicht": StyleSpec(background=(1.0, 1.0, 1.0)),
    "elegant": StyleSpec(
        background=(0.969, 0.949, 0.91), frame_line=(0.66, 0.53, 0.29), title_align="center"
    ),
    "erinnerungen": StyleSpec(background=(0.937, 0.906, 0.855), polaroid=True),
    "magazin": StyleSpec(background=(1.0, 1.0, 1.0)),
}

POLAROID_SIDE_MM = 2.4
POLAROID_BOTTOM_MAX_MM = 8.0
MAX_ROTATION_DEG = 1.6


def polaroid_padding(w: float, h: float) -> tuple[float, float, float]:
    """(seitlich, oben, unten) – unten breiter wie bei einem Sofortbild, skaliert mit der Zelle."""
    side = min(POLAROID_SIDE_MM, w * 0.05, h * 0.05)
    bottom = min(POLAROID_BOTTOM_MAX_MM, h * 0.11)
    return side, side, max(side, bottom)


def rotation_for(image_id: str) -> float:
    """Kleine, aber feste Drehung je Bild (−1,6° … +1,6°) – gleiche ID = gleicher Winkel."""
    value = int(hashlib.md5(image_id.encode()).hexdigest()[:4], 16) / 0xFFFF
    return round((value * 2 - 1) * MAX_ROTATION_DEG, 2)
