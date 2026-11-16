"""Klassifizierung über ein lokales Vision-Modell in Ollama (z. B. qwen2.5vl:7b)."""

import json
from pathlib import Path
from typing import Any

from ollama import AsyncClient

from app.models.album import Classification

PROMPT_TEMPLATE = """Du bist ein erfahrener, kritischer Fotoredakteur und wählst Urlaubsfotos \
für ein hochwertiges Fotobuch aus. Nur wirklich gute Bilder sollen ins Buch.

Bewerte nach gesundem Menschenverstand – so, wie ein Mensch beim Durchblättern entscheiden würde:
- Ist das Motiv klar erkennbar und interessant? Ist das Bild scharf, gut belichtet, gerade?
- Bei Personen: Gesichter gut erkennbar, Augen offen, freundlicher oder natürlicher Ausdruck,
  Personen nicht angeschnitten und nicht winzig im Bild, möglichst gut platziert.
  Ein schönes Foto von Menschen, die lachen, ist mehr wert als eine perfekte Postkartenansicht.
- Bei Sehenswürdigkeiten/Gebäuden: gerade Linien, ganzes Motiv im Bild, gutes Licht.
- Bei Essen: appetitlich, nah, gut beleuchtet.

Antworte als JSON mit diesen Feldern:

1. category: genau EINE Kategorie aus: {categories}.

2. aesthetic_score: ganze Zahl 1–10, streng kalibriert:
   1–3 = misslungen: unscharf, verwackelt, Finger vor der Linse, stark falsch belichtet,
         versehentlich ausgelöst, Boden/Hosentasche fotografiert
   4–5 = gewöhnlicher Schnappschuss: belangloses Motiv, unruhig, schwache Komposition
   6–7 = solides, ansprechendes Urlaubsfoto mit klarem Motiv
   8–9 = sehr gutes Foto: starkes Motiv, gute Komposition UND gutes Licht
   10  = außergewöhnlich, Titelbild-Qualität
   Ein durchschnittliches Handyfoto bekommt 5. Vergib 8 oder mehr nur selten.

3. issues: Liste ALLER zutreffenden Mängel aus:
   blurry (unscharf), motion_blur (verwackelt), overexposed (überbelichtet),
   underexposed (zu dunkel), eyes_closed (jemand hat die Augen geschlossen),
   face_cut_off (Gesicht/Kopf vom Bildrand angeschnitten), unflattering (ungünstiger
   Gesichtsausdruck, Grimasse, Mund voll, halb weggedreht), subject_too_small (Personen
   oder Hauptmotiv winzig), obstructed (Finger/Objekt verdeckt das Bild),
   tilted_horizon (schiefer Horizont oder schiefe Gebäude), cluttered (unruhig/überladen),
   boring (belangloses Motiv), screenshot_or_document (Screenshot, Ticket, Speisekarte,
   Dokument), accidental (versehentlich ausgelöst).
   Leere Liste nur, wenn das Bild wirklich keinen dieser Mängel hat.

4. strengths: Liste zutreffender Stärken aus:
   smiling (Personen lächeln/lachen), natural_expression (natürlicher, entspannter Ausdruck),
   great_light (besonders schönes Licht), golden_hour (Sonnenauf-/-untergangslicht),
   strong_composition (sehr gute Bildaufteilung), iconic_place (bekannte Sehenswürdigkeit
   gut getroffen), emotional_moment (berührender oder lustiger Moment),
   vivid_colors (kräftige, schöne Farben). Leere Liste, wenn nichts davon zutrifft.

5. subject: das Hauptmotiv in 2–4 deutschen Wörtern, so konkret wie möglich
   (z. B. "Eiffelturm", "Galeries Lafayette Kuppel", "Hotelpool", "Pasta Carbonara",
   "Paar am Strand"). Keine Namen von Personen.

6. people: Anzahl der gut sichtbaren Personen (0, wenn keine oder nur winzig im Hintergrund).

7. focus_x, focus_y: Mitte des wichtigsten Bildbereichs als Zahl zwischen 0 und 1
   (focus_x: 0 = linker Rand, 1 = rechter Rand; focus_y: 0 = oben, 1 = unten).
   Bei Personen: die Mitte der Gesichter.

8. reason: ein kurzer deutscher Satz, der die Bewertung begründet.

9. caption: kurze deutsche Bildunterschrift, höchstens 8 Wörter. Nenne den Ort,
   wenn er erkennbar ist (Schild, Sehenswürdigkeit)."""

TITLE_PROMPT = """Du gestaltest ein Urlaubsfotobuch. Die folgenden Fotos gehören zu einem \
Abschnitt (gleiche Zeit, meist gleicher Ort). Je Zeile: Motiv – Bildbeschreibung.

{lines}

Formuliere eine kurze, natürliche Kapitelüberschrift mit 2 bis 5 Wörtern auf Deutsch.
Nenne Ort oder Aktivität so konkret wie möglich, z. B. "Shopping in den Galeries Lafayette",
"Abendessen am Hafen", "Am Strand von Lagos", "Ausflug nach Sintra".
Kein Datum, keine Anführungszeichen, kein Punkt am Ende. Antworte als JSON."""

ALBUM_TITLE_PROMPT = """Du gestaltest den Umschlag eines Urlaubsfotobuchs. Hier sind die \
Kapitelüberschriften und typische Motive der Reise:

{lines}

Wie heißt die Reise? Antworte mit dem Reiseziel in 1 bis 3 Wörtern, so wie man es auf einen
Buchrücken schreibt – z. B. "Paris", "Toskana", "Kreta", "Rom & Florenz", "Norwegen".
Nenne die Stadt oder Region, wenn sie erkennbar ist; sonst eine kurze Beschreibung wie
"Sommer am Meer". Kein Datum, keine Anführungszeichen. Antworte als JSON."""

TITLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}


def build_schema(categories: list[str]) -> dict[str, Any]:
    """JSON-Schema aus dem Pydantic-Modell – Kategorie eingeschränkt, alle Felder Pflicht."""
    schema = Classification.model_json_schema()
    props = schema["properties"]
    props["category"]["enum"] = categories
    props["aesthetic_score"].update({"minimum": 1, "maximum": 10})
    for key in ("focus_x", "focus_y"):
        props[key].update({"minimum": 0, "maximum": 1})
    for prop in props.values():
        prop.pop("default", None)
    schema["required"] = list(props)
    return schema


def clean_title(raw: str) -> str:
    title = raw.strip().strip("\"'„“”«»").rstrip(".!").strip()
    return title[:60]


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

    async def chapter_title(self, descriptions: list[str]) -> str:
        lines = "\n".join(f"- {d}" for d in descriptions[:15])
        response = await self._client.chat(
            model=self._model,
            messages=[{"role": "user", "content": TITLE_PROMPT.format(lines=lines)}],
            format=TITLE_SCHEMA,
            options={"temperature": 0.3},
        )
        data = json.loads(response.message.content or "{}")
        return clean_title(str(data.get("title", "")))

    async def album_title(self, descriptions: list[str]) -> str:
        lines = "\n".join(f"- {d}" for d in descriptions[:25])
        response = await self._client.chat(
            model=self._model,
            messages=[{"role": "user", "content": ALBUM_TITLE_PROMPT.format(lines=lines)}],
            format=TITLE_SCHEMA,
            options={"temperature": 0.2},
        )
        data = json.loads(response.message.content or "{}")
        return clean_title(str(data.get("title", "")))[:30]
