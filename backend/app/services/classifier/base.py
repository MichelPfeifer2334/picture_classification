from pathlib import Path
from typing import Protocol

from app.models.album import Classification


class Classifier(Protocol):
    """Schnittstelle für alle Klassifizierer (Ollama jetzt, später z. B. SigLIP)."""

    async def classify(self, image_path: Path) -> Classification:
        """Bewertet ein einzelnes Bild."""
        ...

    async def chapter_title(self, descriptions: list[str]) -> str:
        """Kurze Kapitelüberschrift aus den Beschreibungen der Bilder eines Abschnitts."""
        ...
