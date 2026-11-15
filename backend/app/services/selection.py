"""Auswahl-Logik: aus Modell-Urteil + technischen Messwerten wird entschieden, was ins Buch kommt.

1. Flags  = Mängel vom Modell ∪ technische Mängel (unscharf, zu dunkel, zu hell)
2. Score  = aesthetic_score − Abzüge je Mangel + Boni je Stärke          (0–10)
3. Rang   = Score + technische Qualität (Schärfe, Belichtung, 0–1)
            → entscheidet, welches Bild einer Gruppe gewinnt
4. Gruppen
   a) Duplikat:        pHash fast gleich                      → nur das beste bleibt
   b) Serie:           pHash ähnlich UND wenige Sekunden      → nur das beste bleibt
   c) Ähnliches Motiv: gleiches Motiv (laut Modell), gleiche Kategorie, zeitnah
                       → das beste bleibt, ein zweites nur, wenn es fast gleich gut ist
5. Auswahl = nicht unterlegen in einer Gruppe UND Score ≥ album.min_score (manuell übersteuerbar)
"""

import re
import statistics
from collections import defaultdict
from collections.abc import Callable

from app.core.config import Settings
from app.models.album import Album, ImageRecord, ImageStatus
from app.services.chapters import assign_chapters

# Abzüge pro Mangel (Punkte auf der 10er-Skala)
PENALTIES: dict[str, float] = {
    "accidental": 4.0,
    "screenshot_or_document": 4.0,
    "blurry": 3.0,
    "motion_blur": 3.0,
    "obstructed": 3.0,
    "eyes_closed": 2.5,
    "face_cut_off": 2.0,
    "overexposed": 2.0,
    "underexposed": 2.0,
    "unflattering": 1.5,
    "boring": 1.5,
    "subject_too_small": 1.0,
    "tilted_horizon": 1.0,
    "cluttered": 1.0,
}

# Boni pro Stärke, gedeckelt
BONUSES: dict[str, float] = {
    "smiling": 0.5,
    "natural_expression": 0.5,
    "emotional_moment": 0.5,
    "great_light": 0.5,
    "golden_hour": 0.5,
    "strong_composition": 0.5,
    "iconic_place": 0.5,
    "vivid_colors": 0.25,
}
MAX_BONUS = 1.5

_STOPWORDS = {
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem", "und", "mit",
    "von", "vor", "am", "im", "in", "an", "auf", "bei", "beim", "zum", "zur", "aus", "the",
}  # fmt: skip


# --- Bausteine -----------------------------------------------------------------------


def _technical_flags(img: ImageRecord, median_sharpness: float | None, s: Settings) -> set[str]:
    m = img.metrics
    if m is None:
        return set()
    flags: set[str] = set()
    if m.sharpness < s.blur_abs or (
        median_sharpness is not None and m.sharpness < s.blur_rel * median_sharpness
    ):
        flags.add("blurry")
    if m.brightness < 45 or m.dark_fraction > 0.6:
        flags.add("underexposed")
    if m.bright_fraction > 0.35:
        flags.add("overexposed")
    return flags


def _score(img: ImageRecord) -> float | None:
    c = img.classification
    if c is None:
        return None
    bonus = min(MAX_BONUS, sum(BONUSES.get(st, 0.0) for st in c.strengths))
    raw = c.aesthetic_score - sum(PENALTIES.get(f, 0.0) for f in img.flags) + bonus
    return round(max(0.0, min(10.0, raw)), 1)


def _technical_quality(img: ImageRecord, median_sharpness: float | None) -> float:
    """0–1: schärfer und ausgewogener belichtet = besser. Für "das hellere/schärfere Bild"."""
    m = img.metrics
    if m is None:
        return 0.5
    reference = (median_sharpness or 200.0) * 1.5
    sharp = min(1.0, m.sharpness / reference) if reference > 0 else 0.5
    exposure = 1.0 - min(1.0, abs(m.brightness - 125.0) / 110.0)
    clipped = min(1.0, (m.dark_fraction + m.bright_fraction) * 2)
    return round(0.55 * sharp + 0.3 * exposure + 0.15 * (1 - clipped), 3)


def _rank(img: ImageRecord, median_sharpness: float | None) -> float:
    base = img.score if img.score is not None else 5.0
    return round(base + _technical_quality(img, median_sharpness), 3)


def _rank_key(img: ImageRecord) -> float:
    return img.rank if img.rank is not None else 0.0


def _union_find(
    items: list[ImageRecord], same: Callable[[ImageRecord, ImageRecord], bool]
) -> list[list[ImageRecord]]:
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a in range(len(items)):
        for b in range(a + 1, len(items)):
            if same(items[a], items[b]):
                parent[find(a)] = find(b)

    groups: dict[int, list[ImageRecord]] = defaultdict(list)
    for idx, img in enumerate(items):
        groups[find(idx)].append(img)
    return list(groups.values())


def _seconds_apart(a: ImageRecord, b: ImageRecord) -> float | None:
    if a.taken_at is None or b.taken_at is None:
        return None
    return abs((a.taken_at - b.taken_at).total_seconds())


def find_groups(images: list[ImageRecord], s: Settings) -> list[list[ImageRecord]]:
    """Duplikate (pHash fast gleich) und Serienbilder (ähnlich + zeitnah)."""
    with_hash = [img for img in images if img.metrics]
    hashes = {img.id: int(img.metrics.phash, 16) for img in with_hash if img.metrics}

    def same(a: ImageRecord, b: ImageRecord) -> bool:
        dist = (hashes[a.id] ^ hashes[b.id]).bit_count()
        if dist <= s.dup_hamming:
            return True
        apart = _seconds_apart(a, b)
        return apart is not None and apart <= s.burst_seconds and dist <= s.burst_hamming

    return _union_find(with_hash, same)


def subject_tokens(subject: str) -> set[str]:
    words = re.findall(r"\w+", subject.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def _similar_subject(a: ImageRecord, b: ImageRecord, s: Settings) -> bool:
    ca, cb = a.classification, b.classification
    if ca is None or cb is None or ca.category != cb.category:
        return False
    ta, tb = subject_tokens(ca.subject), subject_tokens(cb.subject)
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / len(ta | tb)
    apart = _seconds_apart(a, b)
    if apart is None:  # ohne Zeitstempel nur bei identischem Motiv
        return ta == tb
    return overlap >= 0.5 and apart <= s.scene_minutes * 60


# --- Hauptfunktion -----------------------------------------------------------------


def apply_selection(album: Album, s: Settings) -> None:
    """Berechnet flags, score, rank, quality, Gruppen und auto_included (in-place)."""
    sharp = [img.metrics.sharpness for img in album.images if img.metrics]
    median = statistics.median(sharp) if len(sharp) >= 5 else None  # relativ erst ab 5 Bildern

    for img in album.images:
        model_flags = set(img.classification.issues) if img.classification else set()
        img.flags = sorted(model_flags | _technical_flags(img, median, s))
        img.score = _score(img)
        img.rank = _rank(img, median)
        if img.score is None:
            img.quality = None
        else:
            img.quality = "good" if img.score >= 7 else "ok" if img.score >= 5 else "bad"
        img.duplicate_of = None
        img.group_kind = None
        img.group_size = 1

    # a+b) Duplikate und Serien
    for group in find_groups(album.images, s):
        if len(group) < 2:
            continue
        best = max(group, key=_rank_key)
        apart = [_seconds_apart(best, o) for o in group if o is not best]
        is_burst = any(a is not None and a <= s.burst_seconds for a in apart)
        for img in group:
            img.group_size = len(group)
            img.group_kind = "burst" if is_burst else "duplicate"
            img.duplicate_of = None if img is best else best.id

    # c) ähnliches Motiv – nur unter den Gewinnern aus a+b
    leaders = [
        img
        for img in album.images
        if img.duplicate_of is None and img.status == ImageStatus.CLASSIFIED
    ]
    for group in _union_find(leaders, lambda a, b: _similar_subject(a, b, s)):
        if len(group) < 2:
            continue
        ordered = sorted(group, key=_rank_key, reverse=True)
        best = ordered[0]
        keep = [best] + [
            o for o in ordered[1:] if _rank_key(o) >= _rank_key(best) - s.similar_keep_margin
        ]
        keep = keep[: max(1, s.similar_keep)]
        for img in group:
            img.group_size = max(img.group_size, len(group))
            if img in keep:
                if img.group_kind is None:
                    img.group_kind = "similar"
            else:
                img.group_kind = "similar"
                img.duplicate_of = best.id

    for img in album.images:
        good_enough = img.score is None or img.score >= album.min_score
        img.auto_included = (
            img.duplicate_of is None and img.status != ImageStatus.ERROR and good_enough
        )


def curate(album: Album, s: Settings) -> None:
    """Auswahl + Kapitel neu berechnen – nach jeder Änderung am Album aufrufen."""
    apply_selection(album, s)
    assign_chapters(album, s)
