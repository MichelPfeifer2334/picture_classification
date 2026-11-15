from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFilter

from app.core.config import Settings
from app.models.album import Album, Classification, ImageMetrics, ImageRecord, ImageStatus
from app.services.image_processing import compute_metrics
from app.services.selection import apply_selection, subject_tokens

S = Settings()


def _img(
    id_: str,
    score: int = 7,
    issues: list[str] | None = None,
    strengths: list[str] | None = None,
    phash: str = "0000000000000000",
    sharpness: float = 500.0,
    brightness: float = 120.0,
    taken_at: datetime | None = None,
    subject: str = "",
    category: str = "strand",
) -> ImageRecord:
    return ImageRecord(
        id=id_,
        filename=f"{id_}.jpg",
        width=4000,
        height=3000,
        status=ImageStatus.CLASSIFIED,
        classification=Classification.model_validate(
            {
                "category": category,
                "aesthetic_score": score,
                "issues": issues or [],
                "strengths": strengths or [],
                "subject": subject,
                "caption": "x",
            }
        ),
        metrics=ImageMetrics(
            sharpness=sharpness,
            brightness=brightness,
            dark_fraction=0.01,
            bright_fraction=0.01,
            phash=phash,
            taken_at=taken_at,
        ),
    )


def test_penalties_lower_score_and_quality() -> None:
    album = Album(id="a", images=[_img("x", score=7, issues=["blurry", "boring"])])
    apply_selection(album, S)
    img = album.images[0]
    assert img.score == 2.5  # 7 − 3 − 1.5
    assert img.quality == "bad"
    assert not img.included


def test_strengths_add_capped_bonus() -> None:
    many = ["smiling", "great_light", "golden_hour", "strong_composition", "iconic_place"]
    album = Album(id="a", images=[_img("x", score=6, strengths=many)])
    apply_selection(album, S)
    assert album.images[0].score == 7.5  # 6 + max. 1,5


def test_people_issues_penalised() -> None:
    album = Album(id="a", images=[_img("x", score=8, issues=["eyes_closed", "face_cut_off"])])
    apply_selection(album, S)
    assert album.images[0].score == 3.5  # 8 − 2,5 − 2


def test_duplicates_keep_best_only() -> None:
    album = Album(
        id="a",
        images=[
            _img("schlechter", score=6, phash="ffff0000ffff0000"),
            _img("besser", score=8, phash="ffff0000ffff0001"),  # 1 Bit Unterschied
            _img("anders", score=6, phash="0f0f0f0f0f0f0f0f"),
        ],
    )
    apply_selection(album, S)
    imgs = {i.id: i for i in album.images}
    assert imgs["besser"].included and imgs["besser"].group_size == 2
    assert imgs["schlechter"].duplicate_of == "besser" and not imgs["schlechter"].included
    assert imgs["schlechter"].group_kind == "duplicate"
    assert imgs["anders"].included and imgs["anders"].group_size == 1


def test_equal_score_prefers_sharper_and_better_exposed() -> None:
    album = Album(
        id="a",
        images=[
            _img("dunkel", score=7, phash="ffff0000ffff0000", sharpness=200, brightness=50),
            _img("hell", score=7, phash="ffff0000ffff0001", sharpness=600, brightness=125),
        ],
    )
    apply_selection(album, S)
    assert {i.id: i for i in album.images}["dunkel"].duplicate_of == "hell"


def test_burst_groups_by_time() -> None:
    t = datetime(2026, 8, 1, 12, 0, 0)
    # 16 Bit Unterschied: kein Duplikat, aber Serienbild (innerhalb 4 s)
    a = _img("a", score=7, phash="ffffffffffffffff", taken_at=t)
    b = _img("b", score=6, phash="ffffffffffff0000", taken_at=t + timedelta(seconds=2))
    c = _img("c", score=6, phash="ffffffffffff0000", taken_at=t + timedelta(minutes=5))
    album = Album(id="x", images=[a, b])
    apply_selection(album, S)
    assert album.images[1].duplicate_of == "a"
    assert album.images[1].group_kind == "burst"

    album = Album(id="y", images=[a, c])  # zeitlich weit auseinander → keine Serie
    apply_selection(album, S)
    assert album.images[1].duplicate_of is None


def test_similar_subject_keeps_best() -> None:
    t = datetime(2026, 8, 2, 10, 0, 0)
    specs = [  # (id, score, Minuten, Motiv, Kategorie)
        ("e1", 6, 0, "Eiffelturm", "stadt"),
        ("e2", 8, 3, "Der Eiffelturm", "stadt"),
        ("e3", 5, 6, "Eiffelturm bei Tag", "stadt"),
        ("p", 6, 4, "Croissant", "essen"),
    ]
    imgs = [
        _img(i, score=sc, phash=f"{n + 1:x}" * 16, taken_at=t + timedelta(minutes=m),
             subject=subj, category=cat)
        for n, (i, sc, m, subj, cat) in enumerate(specs)
    ]  # fmt: skip
    album = Album(id="a", images=imgs)
    apply_selection(album, S)
    by = {i.id: i for i in album.images}
    assert by["e2"].included
    assert by["e1"].duplicate_of == "e2" and by["e1"].group_kind == "similar"
    assert by["e3"].duplicate_of == "e2"
    assert by["p"].included and by["p"].group_kind is None


def test_similar_keeps_second_if_almost_as_good() -> None:
    t = datetime(2026, 8, 2, 10, 0, 0)
    a = _img("a", score=8, phash="1111111111111111", taken_at=t, subject="Hotelpool")
    b = _img(
        "b",
        score=8,
        phash="2222222222222222",
        taken_at=t + timedelta(minutes=2),
        subject="Hotelpool",
    )
    album = Album(id="x", images=[a, b])
    apply_selection(album, S)
    assert all(i.included for i in album.images)


def test_same_subject_far_apart_is_not_grouped() -> None:
    t = datetime(2026, 8, 2, 10, 0, 0)
    a = _img("a", score=8, phash="1111111111111111", taken_at=t, subject="Strand")
    b = _img(
        "b", score=6, phash="2222222222222222", taken_at=t + timedelta(days=1), subject="Strand"
    )
    album = Album(id="x", images=[a, b])
    apply_selection(album, S)
    assert album.images[1].duplicate_of is None


def test_subject_tokens_ignore_stopwords() -> None:
    assert subject_tokens("Der Eiffelturm am Abend") == {"eiffelturm", "abend"}


def test_relative_blur_detection() -> None:
    imgs = [_img(f"s{i}", phash=f"{i:016x}", sharpness=400.0) for i in range(1, 6)]
    imgs[0].metrics.phash = "aaaaaaaaaaaaaaaa"  # type: ignore[union-attr]
    blurry = _img("weich", phash="5555555555555555", sharpness=50.0)
    album = Album(id="a", images=[*imgs, blurry])
    apply_selection(album, S)
    assert "blurry" in album.images[-1].flags


def test_user_override_wins() -> None:
    img = _img("x", score=3)
    img.user_included = True
    album = Album(id="a", images=[img])
    apply_selection(album, S)
    assert not album.images[0].auto_included
    assert album.images[0].included


def test_sharpness_metric_distinguishes_blur() -> None:
    img = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(img)
    for x in range(0, 800, 20):
        draw.line([x, 0, x, 600], fill="black", width=2)
    sharp = compute_metrics(img).sharpness
    soft = compute_metrics(img.filter(ImageFilter.GaussianBlur(6))).sharpness
    assert sharp > 10 * soft
