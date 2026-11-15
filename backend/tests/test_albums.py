"""End-to-End-Test des Ablaufs mit Fake-Classifier (ohne Ollama)."""

import random
import time
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.api.deps import get_runner, get_store
from app.core.config import Settings
from app.main import app
from app.models.album import Classification
from app.services.jobs import ClassificationRunner
from app.services.storage import AlbumStore

SUBJECTS = ["Leuchtturm", "Hafen", "Kathedrale", "Pizza", "Palmen", "Markt", "Brücke"]


class FakeClassifier:
    def __init__(self) -> None:
        self.n = 0

    async def classify(self, image_path: Path) -> Classification:
        self.n += 1  # unterschiedliche Motive → keine "ähnliches Motiv"-Gruppen
        return Classification(
            category="strand",
            aesthetic_score=7,
            issues=[],
            subject=SUBJECTS[self.n % len(SUBJECTS)],
            reason="scharf",
            caption="Testbild",
        )

    async def chapter_title(self, descriptions: list[str]) -> str:
        return "Testkapitel"


def _jpeg(seed: int, size: tuple[int, int] = (800, 600)) -> bytes:
    """Bild mit eindeutigem, kontrastreichem Muster (scharf, unterscheidbarer pHash)."""
    rnd = random.Random(seed)
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    bw, bh = size[0] // 4, size[1] // 4
    for gx in range(4):  # grobe Helligkeitsblöcke → deutlich verschiedener pHash
        for gy in range(4):
            v = rnd.randint(0, 255)
            draw.rectangle([gx * bw, gy * bh, (gx + 1) * bw, (gy + 1) * bh], fill=(v, v, v))
    for _ in range(30):  # feine Kanten → scharf
        x, y = rnd.randint(0, size[0]), rnd.randint(0, size[1])
        draw.line([x, y, x + 80, y + 10], fill=(rnd.randint(0, 255), 0, 0), width=2)
    buf = BytesIO()
    img.save(buf, "JPEG", quality=95)
    return buf.getvalue()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    store = AlbumStore(tmp_path)
    runner = ClassificationRunner(store, FakeClassifier(), Settings())
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_runner] = lambda: runner
    with TestClient(app) as c:  # Kontextmanager hält den Event-Loop für Hintergrund-Jobs offen
        yield c
    app.dependency_overrides.clear()


def _wait_done(client: TestClient, album_id: str) -> dict:  # type: ignore[type-arg]
    for _ in range(100):
        album = client.get(f"/api/albums/{album_id}").json()
        if album["job"]["status"] == "done":
            return album  # type: ignore[no-any-return]
        time.sleep(0.05)
    raise AssertionError("Job wurde nicht fertig")


def test_full_flow(client: TestClient) -> None:
    album_id = client.post("/api/albums").json()["id"]

    resp = client.post(
        f"/api/albums/{album_id}/images",
        files=[
            ("files", ("a.jpg", _jpeg(1), "image/jpeg")),
            ("files", ("b.jpg", _jpeg(2, (600, 800)), "image/jpeg")),
            ("files", ("notiz.txt", b"hallo", "text/plain")),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["added"]) == 2
    assert body["added"][0]["metrics"]["phash"]
    assert body["errors"][0]["filename"] == "notiz.txt"

    image_id = body["added"][0]["id"]
    for kind in ("thumb", "preview"):
        assert client.get(f"/api/albums/{album_id}/images/{image_id}/{kind}").status_code == 200

    assert client.post(f"/api/albums/{album_id}/classify").json()["total"] == 2
    album = _wait_done(client, album_id)
    assert album["job"]["done"] == 2
    assert all(img["score"] == 7 and img["included"] for img in album["images"])

    layout = client.get(f"/api/albums/{album_id}/layout").json()
    placed = [c["image_id"] for p in layout["pages"] for c in p["cells"]]
    assert sorted(placed) == sorted(img["id"] for img in album["images"])

    pdf = client.get(f"/api/albums/{album_id}/export.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


def test_duplicate_is_excluded(client: TestClient) -> None:
    album_id = client.post("/api/albums").json()["id"]
    same = _jpeg(5)
    client.post(
        f"/api/albums/{album_id}/images",
        files=[
            ("files", ("orig.jpg", same, "image/jpeg")),
            ("files", ("kopie.jpg", same, "image/jpeg")),
            ("files", ("anders.jpg", _jpeg(9), "image/jpeg")),
        ],
    )
    client.post(f"/api/albums/{album_id}/classify")
    album = _wait_done(client, album_id)

    by_name = {img["filename"]: img for img in album["images"]}
    dups = [by_name["orig.jpg"], by_name["kopie.jpg"]]
    assert all(d["group_size"] == 2 for d in dups)
    assert sum(d["included"] for d in dups) == 1  # nur eines der beiden bleibt
    assert by_name["anders.jpg"]["included"]


def test_manual_override_and_min_score(client: TestClient) -> None:
    album_id = client.post("/api/albums").json()["id"]
    up = client.post(
        f"/api/albums/{album_id}/images",
        files=[("files", ("a.jpg", _jpeg(3), "image/jpeg"))],
    ).json()
    image_id = up["added"][0]["id"]
    client.post(f"/api/albums/{album_id}/classify")
    _wait_done(client, album_id)

    # Strenger als Score 7 → automatisch raus
    album = client.patch(f"/api/albums/{album_id}", json={"min_score": 8}).json()
    assert album["images"][0]["included"] is False

    # Manuell wieder rein
    album = client.patch(
        f"/api/albums/{album_id}/images/{image_id}", json={"included": True}
    ).json()
    assert album["images"][0]["included"] is True

    # Zurück auf Automatik
    album = client.patch(
        f"/api/albums/{album_id}/images/{image_id}", json={"included": None}
    ).json()
    assert album["images"][0]["included"] is False

    # Kategorie ändern
    album = client.patch(
        f"/api/albums/{album_id}/images/{image_id}", json={"category": "stadt"}
    ).json()
    assert album["images"][0]["classification"]["category"] == "stadt"
    bad = client.patch(f"/api/albums/{album_id}/images/{image_id}", json={"category": "mond"})
    assert bad.status_code == 422


def test_chapters_get_titles_after_analysis(client: TestClient) -> None:
    album_id = client.post("/api/albums").json()["id"]
    client.post(
        f"/api/albums/{album_id}/images",
        files=[("files", (f"{n}.jpg", _jpeg(n + 20), "image/jpeg")) for n in range(3)],
    )
    client.post(f"/api/albums/{album_id}/classify")
    album = _wait_done(client, album_id)
    assert [c["title"] for c in album["chapters"]] == ["Testkapitel"]

    layout = client.get(f"/api/albums/{album_id}/layout").json()
    assert layout["pages"][0]["title"] == "Testkapitel"

    chapter_id = album["chapters"][0]["id"]
    layout = client.patch(
        f"/api/albums/{album_id}/chapters/{chapter_id}", json={"title": "Am Meer"}
    ).json()
    assert layout["pages"][0]["title"] == "Am Meer"


def test_book_editor_roundtrip(client: TestClient) -> None:
    album_id = client.post("/api/albums").json()["id"]
    ids = [
        img["id"]
        for img in client.post(
            f"/api/albums/{album_id}/images",
            files=[("files", (f"{n}.jpg", _jpeg(n + 40), "image/jpeg")) for n in range(3)],
        ).json()["added"]
    ]
    client.post(f"/api/albums/{album_id}/classify")
    _wait_done(client, album_id)

    # Bild 0 allein auf Seite 1, Bild 1 auf Seite 2, Bild 2 aus dem Buch nehmen
    layout = client.put(
        f"/api/albums/{album_id}/book",
        json={
            "pages": [
                {"template": "single", "image_ids": [ids[0]]},
                {"template": "auto", "image_ids": [ids[1]]},
            ],
            "exclude": [ids[2]],
        },
    ).json()
    assert layout["manual"] is True
    assert [[c["image_id"] for c in p["cells"]] for p in layout["pages"]] == [[ids[0]], [ids[1]]]
    album = client.get(f"/api/albums/{album_id}").json()
    assert not next(i for i in album["images"] if i["id"] == ids[2])["included"]

    # Wieder aufnehmen → erscheint als "nicht platziert"
    client.patch(f"/api/albums/{album_id}/images/{ids[2]}", json={"included": True})
    assert client.get(f"/api/albums/{album_id}/layout").json()["unplaced"] == [ids[2]]

    # Doppelte Bilder werden abgelehnt
    bad = client.put(
        f"/api/albums/{album_id}/book",
        json={"pages": [{"image_ids": [ids[0]]}, {"image_ids": [ids[0]]}]},
    )
    assert bad.status_code == 422

    # Zurücksetzen → automatisch, alles platziert
    layout = client.delete(f"/api/albums/{album_id}/book").json()
    assert layout["manual"] is False and layout["unplaced"] == []


def test_invalid_album_id_returns_404(client: TestClient) -> None:
    assert client.get("/api/albums/../../etc").status_code == 404
    assert client.get("/api/albums/" + "0" * 32).status_code == 404


def test_corrupt_image_is_reported(client: TestClient) -> None:
    album_id = client.post("/api/albums").json()["id"]
    resp = client.post(
        f"/api/albums/{album_id}/images",
        files=[("files", ("kaputt.jpg", b"keinbild", "image/jpeg"))],
    )
    assert resp.json()["added"] == []
    assert "Kein lesbares Bild" in resp.json()["errors"][0]["error"]
