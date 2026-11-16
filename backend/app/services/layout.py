"""Fotobuch-Layout: verteilt die ausgewählten Bilder auf Seiten.

Automatischer Modus
-------------------
1. Reihenfolge = Mini-Kapitel (chronologisch, services/chapters.py).
   Kapitel mit weniger als `chapter_min_images` Bildern im Buch bekommen keine eigene
   Überschrift und laufen auf den Seiten des vorherigen Kapitels weiter.
2. Ein Kapitel mit Überschrift beginnt auf einer neuen Seite; oben steht eine kurze
   Überschrift mit Datum (Platz: `title_band_mm`).
3. Seite für Seite wird die Vorlage gewählt, die am besten zu den nächsten Bildern passt:
   - Highlight (Score ≥ hero_min_score, Querformat) → randlose Ganzseite
   - sonst: geringste Kosten aus
       Seitenverhältnis-Abweichung (wie viel muss beschnitten werden?)
     + Grundgewicht der Vorlage (bevorzugt 2–4 Bilder pro Seite)
     + Abwechslungs-Malus (gleiche Vorlage wie die vorige Seite)
     + Waisen-Malus, wenn danach genau ein Bild allein übrig bliebe (außer Highlight)
     – kleiner Bonus, wenn die besten Bilder in die größten Felder kommen

Manueller Modus
---------------
Hat der Nutzer im Editor etwas geändert, steht in `album.book` eine Seitenliste
(Vorlage + Bild-IDs + Kapitel) und in `album.book_chapters` die Kapitel. Beides wird 1:1
übernommen; nur Bilder, die inzwischen nicht mehr ausgewählt sind, fallen heraus.
Neu ausgewählte Bilder landen in `unplaced`.

Stil
----
Der Stil (services/styles.py) ergänzt pro Zelle Rahmen-Innenabstand und Drehung –
die Seitenaufteilung selbst ist für alle Stile gleich.

Koordinaten in mm, Ursprung oben links an der Endformat-Kante (ohne Beschnitt).
Randlose Zellen reichen um bleed_mm über die Kante hinaus.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from itertools import permutations

from pydantic import BaseModel

from app.core.config import Settings
from app.models.album import Album, BookPage, Chapter, ImageRecord, Style
from app.services.chapters import format_date, split_into_chapters
from app.services.styles import STYLES, polaroid_padding, rotation_for


class Cell(BaseModel):
    image_id: str
    x: float
    y: float
    w: float
    h: float
    focus_x: float = 0.5  # Zuschnitt-Schwerpunkt (0–1), z. B. Gesichter
    focus_y: float = 0.5
    # Stil-Schmuck: Bild liegt um diese Abstände (mm) innerhalb der Zelle, Zelle ist gedreht
    pad_side: float = 0.0
    pad_top: float = 0.0
    pad_bottom: float = 0.0
    rotate: float = 0.0  # Grad, positiv = gegen den Uhrzeigersinn (wie im PDF)


class Page(BaseModel):
    id: str
    template: str
    chapter_id: str
    title: str | None = None
    subtitle: str | None = None
    cells: list[Cell]


class ChapterInfo(BaseModel):
    id: str
    title: str
    subtitle: str | None = None


class BookLayout(BaseModel):
    page_width_mm: float
    page_height_mm: float
    bleed_mm: float
    margin_mm: float
    title_band_mm: float
    style: Style
    manual: bool
    pages: list[Page]
    chapters: list[ChapterInfo]  # in Buchreihenfolge
    unplaced: list[str]  # ausgewählt, aber im manuellen Layout auf keiner Seite


Rect = tuple[float, float, float, float]  # x, y, w, h


@dataclass(frozen=True)
class Template:
    name: str
    slots: int
    bias: float  # Grundkosten – höher = seltener automatisch gewählt
    cells: Callable[[Rect, Settings], list[Rect]]


# --- Vorlagen -------------------------------------------------------------------------


def content_box(s: Settings, with_title: bool = False) -> Rect:
    m = s.margin_mm
    band = s.title_band_mm if with_title else 0.0
    return m, m + band, s.page_width_mm - 2 * m, s.page_height_mm - 2 * m - band


def _two_portrait(c: Rect, s: Settings) -> list[Rect]:
    """Zwei Hochformate nebeneinander – höchstens so hoch, dass die Felder nicht zu schmal sind."""
    x, y, w, h = c
    cw = (w - s.gutter_mm) / 2
    ch = min(h, cw / 0.7)
    cy = y + (h - ch) / 2
    return [(x, cy, cw, ch), (x + cw + s.gutter_mm, cy, cw, ch)]


def _two_landscape(c: Rect, s: Settings) -> list[Rect]:
    x, y, w, h = c
    cw = (w - s.gutter_mm) / 2
    ch = min(h, cw / 1.5)  # 3:2-Zellen, vertikal zentriert
    cy = y + (h - ch) / 2
    return [(x, cy, cw, ch), (x + cw + s.gutter_mm, cy, cw, ch)]


def _two_stack(c: Rect, s: Settings) -> list[Rect]:
    """Zwei Querformate (3:2) übereinander, horizontal zentriert – ideal für quadratische Seiten."""
    x, y, w, h = c
    g = s.gutter_mm
    ch = (h - g) / 2
    cw = min(w, ch * 1.5)
    ch = cw / 1.5
    cx = x + (w - cw) / 2
    cy = y + (h - 2 * ch - g) / 2
    return [(cx, cy, cw, ch), (cx, cy + ch + g, cw, ch)]


def _mixed(c: Rect, s: Settings) -> list[Rect]:
    """Ein Querformat (4:3) neben einem Hochformat (3:4), gleiche Höhe, vertikal zentriert."""
    x, y, w, h = c
    g = s.gutter_mm
    ch = min(h, (w - g) / (4 / 3 + 3 / 4))
    lw, pw = ch * 4 / 3, ch * 3 / 4
    cx = x + (w - g - lw - pw) / 2
    cy = y + (h - ch) / 2
    return [(cx, cy, lw, ch), (cx + lw + g, cy, pw, ch)]


def _three(c: Rect, s: Settings) -> list[Rect]:
    """Großes Bild links (60 %), zwei rechts übereinander."""
    x, y, w, h = c
    g = s.gutter_mm
    big_w = (w - g) * 0.6
    small_w = w - g - big_w
    small_h = (h - g) / 2
    return [
        (x, y, big_w, h),
        (x + big_w + g, y, small_w, small_h),
        (x + big_w + g, y + small_h + g, small_w, small_h),
    ]


def _three_mirror(c: Rect, s: Settings) -> list[Rect]:
    """Wie `three`, aber großes Bild rechts."""
    x, y, w, h = c
    g = s.gutter_mm
    small_w = (w - g) * 0.4
    big_w = w - g - small_w
    small_h = (h - g) / 2
    return [
        (x + small_w + g, y, big_w, h),
        (x, y, small_w, small_h),
        (x, y + small_h + g, small_w, small_h),
    ]


def _three_stack(c: Rect, s: Settings) -> list[Rect]:
    """Ein Hochformat (3:4, volle Höhe) links, zwei Querformate rechts übereinander."""
    x, y, w, h = c
    g = s.gutter_mm
    pw = min(h * 0.75, (w - g) * 0.55)
    rw = w - g - pw
    rh = (h - g) / 2
    return [(x, y, pw, h), (x + pw + g, y, rw, rh), (x + pw + g, y + rh + g, rw, rh)]


def _three_portrait(c: Rect, s: Settings) -> list[Rect]:
    """Drei Hochformate (3:4) nebeneinander, vertikal zentriert."""
    x, y, w, h = c
    g = s.gutter_mm
    cw = (w - 2 * g) / 3
    ch = min(h, cw / 0.75)
    cw = ch * 0.75
    cx = x + (w - 3 * cw - 2 * g) / 2
    cy = y + (h - ch) / 2
    return [(cx + n * (cw + g), cy, cw, ch) for n in range(3)]


def _three_row(c: Rect, s: Settings) -> list[Rect]:
    """Ein breites Feld oben, zwei Bilder darunter (quadratische Seite: Querformat oben,
    Querformat-Seite: Panorama oben)."""
    x, y, w, h = c
    g = s.gutter_mm
    top_h = min((h - g) * 0.62, w / 1.5)
    bottom_h = h - g - top_h
    bw = (w - g) / 2
    return [
        (x, y, w, top_h),
        (x, y + top_h + g, bw, bottom_h),
        (x + bw + g, y + top_h + g, bw, bottom_h),
    ]


def _four(c: Rect, s: Settings) -> list[Rect]:
    x, y, w, h = c
    g = s.gutter_mm
    cw, ch = (w - g) / 2, (h - g) / 2
    return [
        (x, y, cw, ch),
        (x + cw + g, y, cw, ch),
        (x, y + ch + g, cw, ch),
        (x + cw + g, y + ch + g, cw, ch),
    ]


def _four_feature(c: Rect, s: Settings) -> list[Rect]:
    """Ein großes Bild links (58 %), drei kleine rechts übereinander."""
    x, y, w, h = c
    g = s.gutter_mm
    big_w = (w - g) * 0.58
    rw = w - g - big_w
    rh = (h - 2 * g) / 3
    return [(x, y, big_w, h)] + [(x + big_w + g, y + n * (rh + g), rw, rh) for n in range(3)]


def _four_mosaic(c: Rect, s: Settings) -> list[Rect]:
    """Mosaik: großes Querformat oben links, Hochformat rechts (volle Höhe), zwei kleine unten."""
    x, y, w, h = c
    g = s.gutter_mm
    big_w = (w - g) * 0.64
    big_h = (h - g) * 0.64
    right_w = w - g - big_w
    small_w = (big_w - g) / 2
    small_h = h - g - big_h
    return [
        (x, y, big_w, big_h),
        (x + big_w + g, y, right_w, h),
        (x, y + big_h + g, small_w, small_h),
        (x + small_w + g, y + big_h + g, small_w, small_h),
    ]


def _single(c: Rect, s: Settings) -> list[Rect]:
    return [c]  # wird in _geometry passend zum Bild eingepasst (kein Beschnitt)


def _full_bleed(c: Rect, s: Settings) -> list[Rect]:
    b = s.bleed_mm
    return [(-b, -b, s.page_width_mm + 2 * b, s.page_height_mm + 2 * b)]


TEMPLATES: dict[str, Template] = {
    t.name: t
    for t in [
        Template("full_bleed", 1, 0.0, _full_bleed),
        Template("single", 1, 0.6, _single),
        Template("two_portrait", 2, 0.10, _two_portrait),
        Template("two_landscape", 2, 0.15, _two_landscape),
        Template("two_stack", 2, 0.12, _two_stack),
        Template("mixed", 2, 0.15, _mixed),
        Template("three", 3, 0.05, _three),
        Template("three_mirror", 3, 0.07, _three_mirror),
        Template("three_stack", 3, 0.06, _three_stack),
        Template("three_portrait", 3, 0.08, _three_portrait),
        Template("three_row", 3, 0.10, _three_row),
        Template("four", 4, 0.12, _four),
        Template("four_feature", 4, 0.09, _four_feature),
        Template("four_mosaic", 4, 0.10, _four_mosaic),
    ]
}
AUTO_MULTI = [name for name, t in TEMPLATES.items() if t.slots >= 2]
VARIETY_PENALTY = 0.25
ORPHAN_PENALTY = 0.35  # bliebe danach genau ein Bild übrig, stünde es allein auf einer Seite
MAX_MISMATCH = 0.45  # stärker als ~36 % Beschnitt in einer Zelle → automatisch nicht erlaubt
SCORE_TIEBREAK = 0.002


def _mismatch(cell_aspect: float, img_aspect: float) -> float:
    return abs(math.log(cell_aspect) - math.log(img_aspect))


def _best_assignment(
    rects: list[Rect], imgs: list[ImageRecord], strict: bool = True
) -> tuple[float, list[int]]:
    """Zuordnung Bild → Zelle mit möglichst wenig Beschnitt (k ≤ 4 → max. 24 Varianten).

    Bei Gleichstand kommt das bessere Bild ins größere Feld. strict=True verwirft
    Zuordnungen mit zu starkem Beschnitt (Ergebnis dann inf).
    """
    areas = [r[2] * r[3] for r in rects]
    total_area = sum(areas)
    best_cost, best_perm = math.inf, list(range(len(imgs)))
    for perm in permutations(range(len(imgs))):
        costs = [_mismatch(r[2] / r[3], imgs[i].aspect) for r, i in zip(rects, perm, strict=True)]
        if strict and max(costs) > MAX_MISMATCH:
            continue
        prestige = sum(
            a / total_area * (imgs[i].rank or 5.0) for a, i in zip(areas, perm, strict=True)
        )
        cost = sum(costs) / len(imgs) - SCORE_TIEBREAK * prestige
        if cost < best_cost:
            best_cost, best_perm = cost, list(perm)
    return best_cost, best_perm


def _is_hero(img: ImageRecord, s: Settings) -> bool:
    return img.score is not None and img.score >= s.hero_min_score and img.aspect >= 1.2


def _family(name: str) -> str:
    """Vorlagen-Familie für die Abwechslung (three und three_mirror wirken ähnlich)."""
    return name.split("_")[0] if name.startswith(("three", "four")) else name


def _variety(name: str, prev: str) -> float:
    if name == prev:
        return VARIETY_PENALTY
    if prev and _family(name) == _family(prev):
        return VARIETY_PENALTY / 3
    return 0.0


def _orphan(images: list[ImageRecord], next_index: int, s: Settings) -> float:
    """Waisen-Malus: Strafe, wenn nach dieser Seite genau ein Bild im Abschnitt übrig bliebe.

    Ausnahme: Das Restbild ist ein Highlight – das bekommt ohnehin eine eigene Ganzseite.
    """
    if len(images) - next_index != 1 or _is_hero(images[next_index], s):
        return 0.0
    return ORPHAN_PENALTY


def choose_template(
    imgs: list[ImageRecord], content: Rect, s: Settings, prev: str = ""
) -> tuple[str, list[ImageRecord]]:
    """Beste Vorlage für genau diese Bilder (manueller Modus, Vorlage "auto")."""
    if len(imgs) == 1:
        return "single", imgs
    best: tuple[float, str, list[ImageRecord]] = (math.inf, "", imgs)
    for strict in (True, False):
        for name in AUTO_MULTI:
            t = TEMPLATES[name]
            if t.slots != len(imgs):
                continue
            cost, perm = _best_assignment(t.cells(content, s), imgs, strict)
            cost += t.bias + _variety(name, prev)
            if cost < best[0]:
                best = (cost, name, [imgs[p] for p in perm])
        if best[1]:
            break
    return best[1], best[2]


def _paginate(
    images: list[ImageRecord], s: Settings, titled: bool
) -> list[tuple[str, list[ImageRecord]]]:
    """Automatische Seitenaufteilung eines Abschnitts → [(Vorlage, Bilder in Zellreihenfolge)]."""
    pages: list[tuple[str, list[ImageRecord]]] = []
    prev = ""
    i = 0
    while i < len(images):
        first_titled = titled and not pages
        content = content_box(s, with_title=first_titled)
        img = images[i]
        if _is_hero(img, s) and prev != "full_bleed" and not first_titled:
            pages.append(("full_bleed", [img]))
            prev = "full_bleed"
            i += 1
            continue

        remaining = len(images) - i
        best: tuple[float, str, list[ImageRecord]] = (
            (TEMPLATES["single"].bias + _orphan(images, i + 1, s)) if remaining > 1 else 0.0,
            "single",
            [img],
        )
        for name in AUTO_MULTI:
            t = TEMPLATES[name]
            if t.slots > remaining:
                continue
            window = images[i : i + t.slots]
            cost, perm = _best_assignment(t.cells(content, s), window)
            cost += t.bias + _variety(name, prev) + _orphan(images, i + t.slots, s)
            if cost < best[0]:
                best = (cost, name, [window[p] for p in perm])

        _, name, placed = best
        pages.append((name, placed))
        prev = name
        i += len(placed)
    return pages


def _single_fit(img: ImageRecord, c: Rect) -> Rect:
    """Einzelbild ohne Beschnitt, so groß wie möglich im Inhaltsbereich zentriert."""
    x, y, w, h = c
    if img.aspect >= w / h:
        ih = w / img.aspect
        return x, y + (h - ih) / 2, w, ih
    iw = h * img.aspect
    return x + (w - iw) / 2, y, iw, h


def _geometry(
    template: str, imgs: list[ImageRecord], content: Rect, s: Settings, style: Style
) -> list[Cell]:
    rects = TEMPLATES[template].cells(content, s)
    if template == "single":
        rects = [_single_fit(imgs[0], content)]
    decorate = STYLES[style].polaroid and template != "full_bleed"
    cells = []
    for r, img in zip(rects, imgs, strict=False):
        c = img.classification
        cell = Cell(
            image_id=img.id,
            x=round(r[0], 2),
            y=round(r[1], 2),
            w=round(r[2], 2),
            h=round(r[3], 2),
            focus_x=c.focus_x if c else 0.5,
            focus_y=c.focus_y if c else 0.5,
        )
        if decorate:
            side, top, bottom = polaroid_padding(cell.w, cell.h)
            cell.pad_side, cell.pad_top, cell.pad_bottom = (
                round(v, 2) for v in (side, top, bottom)
            )
            cell.rotate = rotation_for(img.id)
        cells.append(cell)
    return cells


# --- Kapitel ---------------------------------------------------------------------------


def _auto_chapters(album: Album, s: Settings) -> list[Chapter]:
    if album.chapters:
        return album.chapters
    # Fallback für Alben ohne berechnete Kapitel
    return [
        Chapter(id=chunk[0].id, start=chunk[0].taken_at, image_ids=[i.id for i in chunk])
        for chunk in split_into_chapters(album.images, s)
    ]


def _chapter_map(album: Album, s: Settings) -> dict[str, Chapter]:
    chapters = {c.id: c for c in _auto_chapters(album, s)}
    if album.book is not None and album.book_chapters is not None:
        chapters.update({c.id: c for c in album.book_chapters})
    return chapters


def _sections(album: Album, s: Settings) -> list[tuple[Chapter, list[ImageRecord]]]:
    """Kapitel mit ihren ausgewählten Bildern; kleine Kapitel hängen am vorherigen."""
    by_id = {img.id: img for img in album.images}
    sections: list[tuple[Chapter, list[ImageRecord]]] = []
    for chapter in _auto_chapters(album, s):
        imgs = [by_id[i] for i in chapter.image_ids if i in by_id and by_id[i].included]
        if not imgs:
            continue
        if len(imgs) < s.chapter_min_images and sections:
            sections[-1][1].extend(imgs)
        else:
            sections.append((chapter, imgs))
    return sections


def auto_pages(album: Album, s: Settings) -> list[BookPage]:
    """Automatisches Layout als Seitenliste (Vorlage + Bild-IDs in Zellreihenfolge)."""
    pages: list[BookPage] = []
    for chapter, imgs in _sections(album, s):
        titled = bool(chapter.title) and (chapter.title_edited or len(imgs) >= s.chapter_min_images)
        for template, placed in _paginate(imgs, s, titled):
            pages.append(
                BookPage(
                    template=template,
                    chapter_id=chapter.id,
                    image_ids=[i.id for i in placed],
                )
            )
    return pages


# --- Aufbau ---------------------------------------------------------------------------


def build_layout(album: Album, s: Settings) -> BookLayout:
    by_id = {img.id: img for img in album.images}
    chapters = _chapter_map(album, s)
    manual = album.book is not None
    specs = album.book if album.book is not None else auto_pages(album, s)

    # Bilder je Kapitel (für Mindestgröße und Datum im manuellen Modus)
    per_chapter: dict[str, list[ImageRecord]] = {}
    for spec in specs:
        imgs = [by_id[i] for i in spec.image_ids if i in by_id and by_id[i].included]
        per_chapter.setdefault(spec.chapter_id, []).extend(imgs)

    def wants_title(chapter: Chapter) -> bool:
        if not chapter.title:
            return False
        if manual:
            return True  # im Editor entscheidet der Nutzer
        return chapter.title_edited or len(per_chapter.get(chapter.id, [])) >= s.chapter_min_images

    def start_of(chapter: Chapter) -> datetime | None:
        times = [i.taken_at for i in per_chapter.get(chapter.id, []) if i.taken_at]
        return min(times) if times else chapter.start

    pages: list[Page] = []
    infos: list[ChapterInfo] = []
    prev_chapter, prev_template = None, ""
    for spec in specs:
        imgs = [by_id[i] for i in spec.image_ids if i in by_id and by_id[i].included][:4]
        if not imgs:
            continue
        chapter = chapters.get(spec.chapter_id)
        starts_chapter = spec.chapter_id != prev_chapter
        subtitle = format_date(start_of(chapter)) if chapter else None
        if starts_chapter:
            infos.append(
                ChapterInfo(
                    id=spec.chapter_id, title=chapter.title if chapter else "", subtitle=subtitle
                )
            )
        title = chapter.title if chapter and starts_chapter and wants_title(chapter) else None

        template = spec.template
        if template not in TEMPLATES or TEMPLATES[template].slots != len(imgs):
            template = "auto"
        with_band = title is not None and template != "full_bleed"
        content = content_box(s, with_title=with_band)
        if template == "auto":
            template, imgs = choose_template(imgs, content, s, prev_template)

        pages.append(
            Page(
                id=f"p{len(pages)}",
                template=template,
                chapter_id=spec.chapter_id,
                title=title,
                subtitle=subtitle if title else None,
                cells=_geometry(template, imgs, content, s, album.style),
            )
        )
        prev_chapter, prev_template = spec.chapter_id, template

    placed = {c.image_id for p in pages for c in p.cells}
    unplaced = [img.id for img in album.images if img.included and img.id not in placed]
    return BookLayout(
        page_width_mm=s.page_width_mm,
        page_height_mm=s.page_height_mm,
        bleed_mm=s.bleed_mm,
        margin_mm=s.margin_mm,
        title_band_mm=s.title_band_mm,
        style=album.style,
        manual=manual,
        pages=pages,
        chapters=infos,
        unplaced=unplaced,
    )
