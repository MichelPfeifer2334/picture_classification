from datetime import datetime, timedelta

from app.core.config import Settings
from app.models.album import Album, Classification, ImageMetrics, ImageRecord, ImageStatus
from app.services.cover import build_cover, date_range
from app.services.layout import build_layout
from app.services.pdf.export import book_sequence
from app.services.print_profile import SAAL_28X28, get_profile, px

T0 = datetime(2026, 8, 14, 10, 0)


def _img(id_: str, rank: float = 7.0, aspect: tuple[int, int] = (4000, 3000)) -> ImageRecord:
    img = ImageRecord(
        id=id_,
        filename=f"{id_}.jpg",
        width=aspect[0],
        height=aspect[1],
        status=ImageStatus.CLASSIFIED,
        classification=Classification(category="stadt", aesthetic_score=7, caption="x"),
        metrics=ImageMetrics(
            sharpness=300,
            brightness=120,
            dark_fraction=0,
            bright_fraction=0,
            phash="0",
            taken_at=T0 + timedelta(days=int(id_[-1])),
        ),
    )
    img.rank = rank
    return img


def test_settings_match_profile() -> None:
    s, p = Settings(), get_profile(Settings().print_profile)
    assert (s.page_width_mm, s.page_height_mm, s.bleed_mm) == (
        p.page_width_mm,
        p.page_height_mm,
        p.bleed_mm,
    )


def test_total_pages_rounds_up_within_limits() -> None:
    p = SAAL_28X28
    assert p.total_pages(0) == 26
    assert p.total_pages(24) == 26  # 24 Fotoseiten + 2 Vorsatz
    assert p.total_pages(25) == 28
    assert p.total_pages(38) == 40
    assert p.total_pages(60) == 40  # Maximum – Preflight meldet den Fehler


def test_cover_geometry_matches_saal_table() -> None:
    album = Album(id="a", images=[_img("i1"), _img("i2")], suggested_title="Paris")
    cover = build_cover(album, SAAL_28X28, content_pages=38)  # → 40 Seiten
    assert cover.pages == 40
    assert abs(cover.width_mm - px(6848)) < 0.01 and abs(cover.height_mm - px(3402)) < 0.01
    g = cover.guides
    assert abs(g.spine_w - px(165)) < 0.01
    assert abs(g.spine_x + g.spine_w / 2 - cover.width_mm / 2) < 0.01  # Rücken mittig
    spine = [t for t in cover.texts if t.rotate]
    assert spine and spine[0].text == "PARIS · 2026" and spine[0].rotate == -90


def test_cover_auto_values() -> None:
    album = Album(id="a", images=[_img("i1", rank=6), _img("i2", rank=9)])
    cover = build_cover(album, SAAL_28X28, content_pages=10)
    assert cover.title == "Unser Urlaub"  # kein Vorschlag vorhanden
    assert cover.subtitle == "August 2026"
    assert cover.front_image_id == "i2"  # bestes Bild vorne
    assert cover.back_image_id == "i1"

    album.cover.spine_direction = "bottom_to_top"
    album.cover.back_image_id = ""
    cover = build_cover(album, SAAL_28X28, content_pages=10)
    assert cover.back_image_id is None
    assert [t.rotate for t in cover.texts if t.rotate] == [90]


def test_all_styles_build_cover() -> None:
    for style in ("schlicht", "elegant", "erinnerungen", "magazin"):
        album = Album(id="a", images=[_img("i1"), _img("i2")], style=style)
        cover = build_cover(album, SAAL_28X28, content_pages=20)
        assert len(cover.images) == 2
        front = cover.images[0]
        assert front.x >= cover.guides.spine_x + cover.guides.spine_w  # Titelbild rechts vom Rücken
        for t in cover.texts:
            if not t.rotate:
                assert t.x >= cover.guides.spine_x + cover.guides.spine_w  # Text nur vorne


def test_date_range_formats() -> None:
    a, b = _img("i1"), _img("i2")
    b.metrics.taken_at = datetime(2026, 9, 2)  # type: ignore[union-attr]
    assert date_range([a, b]) == "August – September 2026"


def test_book_sequence_endpapers_and_padding() -> None:
    imgs = [_img(f"i{n}") for n in range(1, 4)]
    album = Album(id="a", images=imgs)
    layout = build_layout(album, Settings())
    seq, info = book_sequence(layout, SAAL_28X28)
    assert info.total_pages == 26 and len(seq) == 26 and info.sheets == 13
    assert seq[0] is None and seq[-1] is None  # weiße Vorsatzseiten
    assert info.blank_pages == 26 - 2 - info.content_pages
