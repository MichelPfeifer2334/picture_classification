"""Datenmodelle des MVP. Persistiert wird als JSON-Datei pro Album (kein SQLite im MVP)."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Classification(BaseModel):
    """Antwort des Vision-Modells – dieses Schema wird Ollama als JSON-Format vorgegeben."""

    category: str = Field(description="Genau eine Kategorie aus der vorgegebenen Liste")
    quality: Literal["good", "ok", "bad"] = Field(description="Eignung fürs Fotobuch")
    quality_reason: str = Field(description="Kurze Begründung der Qualitätsbewertung")
    caption: str = Field(description="Kurze deutsche Bildunterschrift, max. 8 Wörter")


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


class JobState(BaseModel):
    status: Literal["idle", "running", "done"] = "idle"
    done: int = 0
    total: int = 0


class Album(BaseModel):
    id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    images: list[ImageRecord] = []
    job: JobState = JobState()

    def find_image(self, image_id: str) -> ImageRecord | None:
        return next((img for img in self.images if img.id == image_id), None)


class UploadError(BaseModel):
    filename: str
    error: str


class UploadResult(BaseModel):
    added: list[ImageRecord]
    errors: list[UploadError]
