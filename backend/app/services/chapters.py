"""Mini-Kapitel: teilt den Urlaub chronologisch in zusammenhängende Abschnitte.

Regeln
------
- Sortiert nach EXIF-Aufnahmezeit.
- Neues Kapitel, wenn zwischen zwei Bildern mehr als `chapter_gap_minutes` liegen
  oder ein neuer Tag beginnt (Tageswechsel um 4 Uhr – Nachtaufnahmen zählen zum Vortag).
- Kapitel mit mehr als `chapter_max_images` Bildern werden an der größten Zeitlücke geteilt.
- Bilder ohne Zeitstempel kommen ans Ende, gruppiert nach Kategorie.
- Titel bleiben erhalten, wenn ein neu berechnetes Kapitel überwiegend dieselben Bilder enthält.
"""

from datetime import date, datetime, timedelta

from app.core.config import Settings
from app.models.album import Album, Chapter, ImageRecord

_MONTHS = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]  # fmt: skip
_DAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
DAY_START = timedelta(hours=4)


def format_date(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return f"{_DAYS[dt.weekday()]}, {dt.day}. {_MONTHS[dt.month - 1]} {dt.year}"


def _day(dt: datetime) -> date:
    return (dt - DAY_START).date()


def _split_long(chunk: list[ImageRecord], max_len: int) -> list[list[ImageRecord]]:
    if len(chunk) <= max_len:
        return [chunk]
    gaps = [
        (chunk[i + 1].taken_at - chunk[i].taken_at, i)  # type: ignore[operator]
        for i in range(len(chunk) - 1)
    ]
    _, k = max(gaps)
    return _split_long(chunk[: k + 1], max_len) + _split_long(chunk[k + 1 :], max_len)


def split_into_chapters(images: list[ImageRecord], s: Settings) -> list[list[ImageRecord]]:
    timed = sorted((i for i in images if i.taken_at), key=lambda i: (i.taken_at, i.filename))
    untimed = sorted((i for i in images if not i.taken_at), key=lambda i: i.filename)

    chunks: list[list[ImageRecord]] = []
    current: list[ImageRecord] = []
    gap = timedelta(minutes=s.chapter_gap_minutes)
    for img in timed:
        if current:
            prev, now = current[-1].taken_at, img.taken_at
            assert prev is not None and now is not None
            if now - prev > gap or _day(now) != _day(prev):
                chunks.append(current)
                current = []
        current.append(img)
    if current:
        chunks.append(current)

    result = [part for chunk in chunks for part in _split_long(chunk, s.chapter_max_images)]

    # ohne Zeitstempel: nach Kategorie (Reihenfolge wie konfiguriert)
    order = {c: n for n, c in enumerate(s.categories)}
    by_cat: dict[str, list[ImageRecord]] = {}
    for img in untimed:
        cat = img.classification.category if img.classification else s.categories[-1]
        by_cat.setdefault(cat, []).append(img)
    for cat in sorted(by_cat, key=lambda c: order.get(c, len(order))):
        result.extend(_split_long_untimed(by_cat[cat], s.chapter_max_images))
    return result


def _split_long_untimed(chunk: list[ImageRecord], max_len: int) -> list[list[ImageRecord]]:
    return [chunk[i : i + max_len] for i in range(0, len(chunk), max_len)]


def assign_chapters(album: Album, s: Settings) -> None:
    """Kapitel neu berechnen und vorhandene Titel übernehmen (in-place)."""
    old = album.chapters
    new: list[Chapter] = []
    for chunk in split_into_chapters(album.images, s):
        ids = [img.id for img in chunk]
        chapter = Chapter(id=ids[0], start=chunk[0].taken_at, image_ids=ids)
        best, best_overlap = None, 0.0
        for prev in old:
            overlap = len(set(ids) & set(prev.image_ids)) / max(len(ids), 1)
            if overlap > best_overlap:
                best, best_overlap = prev, overlap
        if best is not None and best_overlap >= 0.5:
            chapter.title, chapter.title_edited = best.title, best.title_edited
            if best.title_edited:
                chapter.id = best.id  # Nutzer-Titel stabil halten
        new.append(chapter)
    # IDs eindeutig halten (falls ein alter Titel an zwei neue Kapitel vererbt wurde)
    seen: set[str] = set()
    for chapter in new:
        if chapter.id in seen:
            chapter.id = chapter.image_ids[0]
        seen.add(chapter.id)
    album.chapters = new


def fallback_title(images: list[ImageRecord]) -> str:
    """Titel ohne Modell: häufigstes Motiv im Kapitel."""
    subjects: dict[str, int] = {}
    for img in images:
        if img.classification and img.classification.subject:
            key = img.classification.subject.strip()
            subjects[key] = subjects.get(key, 0) + 1
    if not subjects:
        return ""
    return max(subjects.items(), key=lambda kv: kv[1])[0][:60]
