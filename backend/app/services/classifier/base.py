from pathlib import Path
from typing import Protocol

from app.models.album import Classification


class Classifier(Protocol):
    """Schnittstelle für alle Klassifizierer (Ollama jetzt, später z. B. SigLIP)."""

    async def classify(self, image_path: Path) -> Classification: ...
