"""Datenmodelle. Persistiert wird als JSON-Datei pro Album (kein SQLite)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, get_args

from pydantic import BaseModel, Field, computed_field, field_validator

# Mängel, die das Modell melden darf (Schlüssel englisch, Labels macht das Frontend)
Issue = Literal[
    "blurry",
    "motion_blur",
    "overexposed",
    "underexposed",
    "eyes_closed",
    "face_cut_off",
    "unflattering",
    "subject_too_small",
    "obstructed",
    "tilted_horizon",
    "cluttered",
    "boring",
    "screenshot_or_document",
    "accidental",
]
ISSUES: tuple[str, ...] = get_args(Issue)

# Stärken, die Pluspunkte bringen
Strength = Literal[
    "smiling",
    "natural_expression",
    "great_light",
    "golden_hour",
    "strong_composition",
    "iconic_place",
    "emotional_moment",
    "vivid_colors",
]
STRENGTHS: tuple[str, ...] = get_args(Strength)

Quality = Literal["good", "ok", "bad"]
GroupKind = Literal["duplicate", "burst", "similar"]

# Gestaltungsstile des Fotobuchs (siehe services/pdf/styles.py und docs/06-pdf-fotobuch.md)
Style = Literal["schlicht", "elegant", "erinnerungen", "magazin"]
SpineDirection = Literal["top_to_bottom", "bottom_to_top"]


def _clamp01(v: Any) -> float:
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.5


class Classification(BaseModel):
    """Antwort des Vision-Modells – dieses Schema wird Ollama als JSON-Format vorgegeben."""

    category: str = Field(description="Genau eine Kategorie aus der vorgegebenen Liste")
    aesthetic_score: int = Field(default=5, description="Fotobuch-Eignung 1–10, streng")
    issues: list[Issue] = Field(default=[], description="Alle zutreffenden Mängel")
    strengths: list[Strength] = Field(default=[], description="Besondere Stärken des Bildes")
    subject: str = Field(default="", description="Hauptmotiv in 2–4 Wörtern")
    people: int = Field(default=0, description="Anzahl gut sichtbarer Personen")
    focus_x: float = Field(default=0.5, description="Mitte des Hauptmotivs, 0 = links, 1 = rechts")
    focus_y: float = Field(default=0.5, description="Mitte des Hauptmotivs, 0 = oben, 1 = unten")
    reason: str = Field(default="", description="Kurze deutsche Begründung")
    caption: str = Field(default="", description="Kurze deutsche Bildunterschrift")

    @field_validator("aesthetic_score", mode="before")
    @classmethod
    def _clamp_score(cls, v: Any) -> int:
        try:
            return max(1, min(10, round(float(v))))
        except (TypeError, ValueError):
            return 5

    @field_validator("people", mode="before")
    @classmethod
    def _people(cls, v: Any) -> int:
        try:
            return max(0, min(50, int(v)))
        except (TypeError, ValueError):
            return 0

    @field_validator("focus_x", "focus_y", mode="before")
    @classmethod
    def _focus(cls, v: Any) -> float:
        return _clamp01(v)

    @field_validator("issues", mode="before")
    @classmethod
    def _known_issues(cls, v: Any) -> list[str]:
        return [i for i in (v or []) if i in ISSUES]

    @field_validator("strengths", mode="before")
    @classmethod
    def _known_strengths(cls, v: Any) -> list[str]:
        return [i for i in (v or []) if i in STRENGTHS]


class ImageMetrics(BaseModel):
    """Technische Messwerte, berechnet ohne KI beim Upload."""

    sharpness: float  # Laplace-Varianz (90. Perzentil über 4×4 Kacheln)
    brightness: float  # mittlere Helligkeit 0–255
    dark_fraction: float  # Anteil fast schwarzer Pixel
    bright_fraction: float  # Anteil fast weißer Pixel
    phash: str  # Perceptual Hash (64 Bit, hex) für Duplikate
    taken_at: datetime | None = None  # EXIF-Aufnahmezeit


class ImageStatus(StrEnum):
    UPLOADED = "uploaded"
    CLASSIFIED = "classified"
    ERROR = "error"


class ImageRecord(BaseModel):
    id: str
    filename: str
    width: int
    height: int
    status: ImageStatus = ImageStatus.UPLOADED
    classification: Classification | None = None
    error: str | None = None
    metrics: ImageMetrics | None = None

    # --- Ergebnis der Auswahl (services/selection.py) ---
    score: float | None = None  # Gesamtscore 0–10 (Modell − Abzüge + Boni)
    rank: float | None = None  # Score + technische Qualität – entscheidet innerhalb von Gruppen
    quality: Quality | None = None
    flags: list[str] = []  # Mängel aus Modell + Technik
    duplicate_of: str | None = None  # ID des Bildes, das in der Gruppe gewonnen hat
    group_kind: GroupKind | None = None  # Art der Gruppe (Duplikat, Serie, ähnliches Motiv)
    group_size: int = 1
    auto_included: bool = True  # Vorschlag der Automatik
    user_included: bool | None = None  # manuelle Übersteuerung (None = Automatik)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def included(self) -> bool:
        return self.auto_included if self.user_included is None else self.user_included

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0

    @property
    def taken_at(self) -> datetime | None:
        return self.metrics.taken_at if self.metrics else None


class JobState(BaseModel):
    status: Literal["idle", "running", "done"] = "idle"
    phase: Literal["analyze", "titles"] = "analyze"
    done: int = 0
    total: int = 0
    started_at: datetime | None = None


class Chapter(BaseModel):
    """Mini-Kapitel: zeitlich zusammenhängende Bilder (z. B. ein Nachmittag in der Stadt)."""

    id: str
    title: str = ""
    title_edited: bool = False  # vom Nutzer geändert → nie automatisch überschreiben
    start: datetime | None = None
    image_ids: list[str] = []


class BookPage(BaseModel):
    """Eine Seite im manuell bearbeiteten Fotobuch."""

    template: str = "auto"  # "auto" = passende Vorlage automatisch wählen
    chapter_id: str = ""
    image_ids: list[str] = []


class CoverSettings(BaseModel):
    """Umschlag. `None` heißt jeweils: automatisch bestimmen."""

    title: str | None = None  # None = Vorschlag des Modells (album.suggested_title)
    subtitle: str | None = None  # None = Zeitraum aus den Aufnahmedaten, "" = keiner
    spine_text: str | None = None  # None = "TITEL · JAHR", "" = kein Text
    front_image_id: str | None = None  # None = bestes Bild
    back_image_id: str | None = None  # None = automatisch, "" = kein Bild
    spine_direction: SpineDirection = "top_to_bottom"


class Album(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None  # wird bei jedem Speichern gesetzt
    name: str = ""  # vom Nutzer vergebener Name
    saved: bool = False  # bewusst gespeichert → erscheint in der Album-Liste
    images: list[ImageRecord] = []
    job: JobState = JobState()
    min_score: float = 6.0
    chapters: list[Chapter] = []
    book: list[BookPage] | None = None  # None = Layout automatisch, sonst manuell bearbeitet
    book_chapters: list[Chapter] | None = None  # Kapitel im manuellen Layout (Editor)
    style: Style = "schlicht"
    suggested_title: str = ""  # Albumtitel-Vorschlag des Modells, z. B. "Paris"
    cover: CoverSettings = CoverSettings()

    def find_image(self, image_id: str) -> ImageRecord | None:
        return next((img for img in self.images if img.id == image_id), None)

    def find_chapter(self, chapter_id: str) -> Chapter | None:
        """Sucht zuerst in den Editor-Kapiteln (falls manuell), dann in den automatischen."""
        for chapters in (self.book_chapters or [], self.chapters):
            found = next((c for c in chapters if c.id == chapter_id), None)
            if found is not None:
                return found
        return None


# --- Request/Response-Modelle ---------------------------------------------------


class UploadError(BaseModel):
    filename: str
    error: str


class UploadResult(BaseModel):
    added: list[ImageRecord]
    errors: list[UploadError]


class AlbumUpdate(BaseModel):
    min_score: float | None = Field(default=None, ge=0, le=10)
    style: Style | None = None
    name: str | None = Field(default=None, max_length=80)
    saved: bool | None = None


class AlbumSummary(BaseModel):
    """Kurzinfo für die Album-Liste auf der Startseite."""

    id: str
    name: str
    saved: bool
    created_at: datetime
    updated_at: datetime | None
    image_count: int
    selected_count: int
    classified: bool  # mindestens ein Bild analysiert
    thumb_image_id: str | None  # Titelbild für die Karte
    running: bool = False


class CleanupResult(BaseModel):
    deleted: int


class ImageUpdate(BaseModel):
    """`included: null` setzt auf Automatik zurück; nicht gesendete Felder bleiben unverändert."""

    included: bool | None = None
    category: str | None = None


class CoverUpdate(BaseModel):
    """Nur gesendete Felder werden übernommen; `null` setzt ein Feld auf Automatik zurück."""

    title: str | None = Field(default=None, max_length=40)
    subtitle: str | None = Field(default=None, max_length=60)
    spine_text: str | None = Field(default=None, max_length=40)
    front_image_id: str | None = None
    back_image_id: str | None = None
    spine_direction: SpineDirection | None = None


class ChapterUpdate(BaseModel):
    title: str = Field(max_length=80)


class BookChapter(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(default="", max_length=80)


class BookUpdate(BaseModel):
    """Manuelles Layout speichern. include/exclude ändern zugleich die Auswahl einzelner Bilder.

    `chapters` (optional) legt die Kapitel des manuellen Layouts fest – so lassen sich Kapitel
    im Editor teilen und zusammenführen.
    """

    pages: list[BookPage]
    chapters: list[BookChapter] | None = None
    include: list[str] = []
    exclude: list[str] = []
