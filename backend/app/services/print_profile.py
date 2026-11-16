"""Anbieterprofile: Format- und Druckvorgaben eines Fotobuch-Anbieters.

Das Profil bestimmt, wie Innenteil und Umschlag als PDF geliefert werden
(Einzel- oder Doppelseiten, Seitenzahl-Regeln, Rückenbreite je Seitenzahl, Beschnitt, Falz).
Die Seitengröße selbst steht zusätzlich in `Settings` (page_width_mm/page_height_mm/bleed_mm),
weil das Layout damit rechnet – ein Test stellt sicher, dass beides übereinstimmt.

Werte für Saal Digital 28 × 28 aus den Saal-Vorlagen (IDML) und der Maßtabelle,
siehe docs/06-pdf-fotobuch.md.
"""

from dataclasses import dataclass

PX_PER_MM = 300 / 25.4  # Saal gibt Maße in Pixeln bei 300 dpi an


def px(value: float) -> float:
    """Pixel (300 dpi) → mm."""
    return value / PX_PER_MM


@dataclass(frozen=True)
class SpineStep:
    max_pages: int  # gilt bis einschließlich dieser Seitenzahl
    spine_px: int  # Rückenbreite
    width_px: int  # Gesamtbreite der Umschlagdatei inkl. Beschnitt


@dataclass(frozen=True)
class CoverSpec:
    height_px: int  # Gesamthöhe der Umschlagdatei inkl. Beschnitt
    bleed_lr_px: int  # Beschnitt links/rechts (Einschlag um die Pappe)
    bleed_tb_px: int  # Beschnitt oben/unten
    fold_px: int  # Falz (Gelenk) links und rechts neben dem Rücken
    steps: tuple[SpineStep, ...]

    def step_for(self, pages: int) -> SpineStep:
        for step in self.steps:
            if pages <= step.max_pages:
                return step
        return self.steps[-1]


@dataclass(frozen=True)
class PrintProfile:
    id: str
    name: str
    page_width_mm: float  # Endformat einer Seite
    page_height_mm: float
    bleed_mm: float  # Beschnitt des Innenteils
    spreads: bool  # True: eine PDF-Seite pro Doppelseite
    blank_endpapers: bool  # 1. und letzte Seite kleben auf den Deckeln → weiß lassen
    min_pages: int
    max_pages: int
    page_step: int
    safe_mm: float  # Sicherheitsabstand für Text/Gesichter zum Endformat
    cover: CoverSpec

    @property
    def max_content_pages(self) -> int:
        return self.max_pages - (2 if self.blank_endpapers else 0)

    def total_pages(self, content_pages: int) -> int:
        """Kleinste erlaubte Seitenzahl, in die `content_pages` Fotoseiten passen."""
        needed = content_pages + (2 if self.blank_endpapers else 0)
        pages = self.min_pages
        while pages < needed and pages < self.max_pages:
            pages += self.page_step
        return pages


SAAL_28X28 = PrintProfile(
    id="saal_28x28",
    name="Saal Digital · Fotobuch 28 × 28 · Hardcover",
    page_width_mm=270.0,
    page_height_mm=270.0,
    bleed_mm=3.0,
    spreads=True,
    blank_endpapers=True,
    min_pages=26,
    max_pages=40,
    page_step=2,
    safe_mm=10.0,
    cover=CoverSpec(
        height_px=3402,
        bleed_lr_px=110,
        bleed_tb_px=83,
        fold_px=106,
        steps=(
            SpineStep(30, 142, 6833),
            SpineStep(32, 154, 6833),
            SpineStep(36, 154, 6848),
            SpineStep(40, 165, 6848),
        ),
    ),
)

PROFILES: dict[str, PrintProfile] = {p.id: p for p in (SAAL_28X28,)}


def get_profile(profile_id: str) -> PrintProfile:
    return PROFILES[profile_id]
