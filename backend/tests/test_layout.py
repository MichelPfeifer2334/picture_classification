from datetime import datetime, timedelta

from app.core.config import Settings
from app.models.album import (
    Album,
    BookPage,
    Classification,
    ImageMetrics,
    ImageRecord,
    ImageStatus,
)
from app.services.chapters import assign_chapters, split_into_chapters
from app.services.layout import build_layout

S = Settings()
T0 = datetime(2026, 8, 1, 10, 0, 0)


def _img(
    id_: str,
    w: int,
    h: int,
    score: float = 7.0,
    taken_at: datetime | None = None,
    focus: tuple[float, float] = (0.5, 0.5),
) -> ImageRecord:
    img = ImageRecord(
        id=id_,
        filename=f"{id_}.jpg",
        width=w,
        height=h,
        status=ImageStatus.CLASSIFIED,
        classification=Classification(
            category="strand", aesthetic_score=7, caption="x", focus_x=focus[0], focus_y=focus[1]
        ),
        metrics=ImageMetrics(
            sharpness=300, brightness=120, dark_fraction=0, bright_fraction=0, phash="0",
            taken_at=taken_at,
        ),
    )  # fmt: skip
    img.score = score
    return img


def _album(imgs: list[ImageRecord]) -> Album:
    album = Album(id="a", images=imgs)
    assign_chapters(album, S)
    return album


def test_every_included_image_placed_exactly_once() -> None:
    imgs = [_img(f"i{n}", 4000, 3000) if n % 3 else _img(f"i{n}", 3000, 4000) for n in range(11)]
    imgs[4].user_included = False
    layout = build_layout(_album(imgs), S)
    placed = [c.image_id for p in layout.pages for c in p.cells]
    assert sorted(placed) == sorted(i.id for i in imgs if i.included)
    assert all(1 <= len(p.cells) <= 4 for p in layout.pages)
    assert layout.unplaced == []


def test_hero_gets_full_bleed_page() -> None:
    layout = build_layout(_album([_img("hero", 4000, 3000, score=9.0)]), S)
    page = layout.pages[0]
    assert page.template == "full_bleed"
    assert page.cells[0].x == -S.bleed_mm and page.cells[0].w == S.page_width_mm + 2 * S.bleed_mm


def test_two_portraits_share_a_page() -> None:
    layout = build_layout(_album([_img("p1", 3000, 4000), _img("p2", 3000, 4000)]), S)
    assert [p.template for p in layout.pages] == ["two_portrait"]


def test_focus_is_passed_to_cells() -> None:
    layout = build_layout(_album([_img("p", 3000, 4000, focus=(0.2, 0.3))]), S)
    cell = layout.pages[0].cells[0]
    assert (cell.focus_x, cell.focus_y) == (0.2, 0.3)


def test_chapters_split_on_time_gap_and_day() -> None:
    imgs = [
        _img("a", 4000, 3000, taken_at=T0),
        _img("b", 4000, 3000, taken_at=T0 + timedelta(minutes=20)),
        _img("c", 4000, 3000, taken_at=T0 + timedelta(hours=4)),  # Lücke > 90 min
        _img("d", 4000, 3000, taken_at=T0 + timedelta(hours=4, minutes=5)),
        _img("e", 4000, 3000, taken_at=T0.replace(hour=23, minute=30)),  # gleicher Tag
        _img(
            "f", 4000, 3000, taken_at=T0.replace(day=2, hour=0, minute=30)
        ),  # nach Mitternacht → Vortag
        _img("g", 4000, 3000, taken_at=T0.replace(day=2, hour=9)),  # neuer Tag
    ]
    chunks = split_into_chapters(imgs, S)
    assert [[i.id for i in c] for c in chunks] == [["a", "b"], ["c", "d"], ["e", "f"], ["g"]]


def test_titled_chapter_starts_new_page_with_title_band() -> None:
    imgs = [_img(f"a{n}", 4000, 3000, taken_at=T0 + timedelta(minutes=n)) for n in range(3)]
    imgs += [
        _img(f"b{n}", 4000, 3000, taken_at=T0 + timedelta(hours=5, minutes=n)) for n in range(4)
    ]
    album = _album(imgs)
    album.chapters[1].title = "Abendessen am Hafen"
    layout = build_layout(album, S)

    titled = [p for p in layout.pages if p.title]
    assert [p.title for p in titled] == ["Abendessen am Hafen"]
    assert titled[0].subtitle == "Samstag, 1. August 2026"
    assert all(c.y >= S.margin_mm + S.title_band_mm - 0.01 for c in titled[0].cells)
    # Kapitel b beginnt auf eigener Seite
    first_b = layout.pages.index(titled[0])
    assert all(c.image_id.startswith("b") for c in titled[0].cells)
    assert all(c.image_id.startswith("a") for p in layout.pages[:first_b] for c in p.cells)


def test_small_chapter_gets_no_title() -> None:
    imgs = [_img(f"a{n}", 4000, 3000, taken_at=T0 + timedelta(minutes=n)) for n in range(4)]
    imgs += [_img("b0", 4000, 3000, taken_at=T0 + timedelta(hours=5))]
    album = _album(imgs)
    album.chapters[1].title = "Nur ein Bild"
    layout = build_layout(album, S)
    assert all(p.title != "Nur ein Bild" for p in layout.pages)


def test_titles_survive_rechaptering() -> None:
    imgs = [_img(f"a{n}", 4000, 3000, taken_at=T0 + timedelta(minutes=n)) for n in range(3)]
    album = _album(imgs)
    album.chapters[0].title = "Am Strand"
    album.images.append(_img("a9", 4000, 3000, taken_at=T0 + timedelta(minutes=10)))
    assign_chapters(album, S)
    assert album.chapters[0].title == "Am Strand"


def test_manual_book_is_respected_and_reports_unplaced() -> None:
    imgs = [_img(f"i{n}", 4000, 3000, taken_at=T0 + timedelta(minutes=n)) for n in range(4)]
    album = _album(imgs)
    chapter = album.chapters[0].id
    album.book = [
        BookPage(template="single", chapter_id=chapter, image_ids=["i2"]),
        BookPage(template="two_landscape", chapter_id=chapter, image_ids=["i1", "i0"]),
    ]
    layout = build_layout(album, S)
    assert layout.manual
    assert [[c.image_id for c in p.cells] for p in layout.pages] == [["i2"], ["i1", "i0"]]
    assert layout.unplaced == ["i3"]


def test_manual_page_with_wrong_count_gets_auto_template() -> None:
    imgs = [_img(f"i{n}", 3000, 4000, taken_at=T0 + timedelta(minutes=n)) for n in range(2)]
    album = _album(imgs)
    album.book = [BookPage(template="four", chapter_id="", image_ids=["i0", "i1"])]
    layout = build_layout(album, S)
    assert layout.pages[0].template == "two_portrait"


def test_cells_stay_inside_page() -> None:
    imgs = [_img(f"i{n}", 4000, 3000 if n % 2 else 4500) for n in range(9)]
    layout = build_layout(_album(imgs), S)
    for page in layout.pages:
        if page.template == "full_bleed":
            continue
        for c in page.cells:
            assert c.x >= S.margin_mm - 0.01 and c.y >= S.margin_mm - 0.01
            assert c.x + c.w <= S.page_width_mm - S.margin_mm + 0.01
            assert c.y + c.h <= S.page_height_mm - S.margin_mm + 0.01
