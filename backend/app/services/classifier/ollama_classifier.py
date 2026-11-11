"""Klassifizierung über ein lokales Vision-Modell in Ollama (z. B. qwen2.5vl:7b)."""

from pathlib import Path
from typing import Any

from ollama import AsyncClient

from app.models.album import Classification

PROMPT_TEMPLATE = """Du bewertest Urlaubsfotos für ein Fotobuch.

1. Ordne das Bild genau EINER Kategorie zu: {categories}.
2. Bewerte die Eignung fürs Fotobuch als "good", "ok" oder "bad".
   "bad" = unscharf, verwackelt, stark über- oder unterbelichtet, Finger vor der Linse,
   Augen geschlossen, schiefer Horizont oder belangloses Motiv.
3. Begründe die Bewertung in einem kurzen deutschen Satz (quality_reason).
4. Schreibe eine kurze deutsche Bildunterschrift mit höchstens 8 Wörtern (caption).

Antworte ausschließlich als JSON."""


def build_schema(categories: list[str]) -> dict[str, Any]:
    """JSON-Schema aus dem Pydantic-Modell, Kategorie auf die erlaubte Liste eingeschränkt."""
    schema = Classification.model_json_schema()
    schema["properties"]["category"]["enum"] = categories
    return schema


class OllamaClassifier:
    def __init__(self, host: str, model: str, categories: list[str], timeout_s: float) -> None:
        self._client = AsyncClient(host=host, timeout=timeout_s)
        self._model = model
        self._categories = categories
        self._schema = build_schema(categories)
        self._prompt = PROMPT_TEMPLATE.format(categories=", ".join(categories))

    async def classify(self, image_path: Path) -> Classification:
        response = await self._client.chat(
            model=self._model,
            messages=[
                {"role": "user", "content": self._prompt, "images": [image_path.read_bytes()]}
            ],
            format=self._schema,  # erzwingt Antwort im JSON-Schema
            options={"temperature": 0},
        )
        result = Classification.model_validate_json(response.message.content or "")
        if result.category not in self._categories:
            result.category = self._categories[-1]  # Fallback: "sonstiges"
        return result
