"""End-to-End-Test des MVP-Ablaufs mit Fake-Classifier (ohne Ollama)."""

import time
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.deps import get_runner, get_store
from app.main import app
from app.models.album import Classification
from app.services.jobs import ClassificationRunner
from app.services.storage import AlbumStore


class FakeClassifier:
    async def classify(self, image_path: Path) -> Classification:
        return Classification(
            category="strand", quality="good", quality_reason="scharf", caption="Testbild"
        )


def _jpeg(color: str) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (800, 600), color).save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    store = AlbumStore(tmp_path)
    runner = ClassificationRunner(store, FakeClassifier())
    app.dependency_overrides[get_store] = lambda: store
    app.dependency_overrides[get_runner] = lambda: runner
    with TestClient(app) as c:  # Kontextmanager hält den Event-Loop für Hintergrund-Jobs offen
        yield c
    app.dependency_overrides.clear()


def test_full_flow(client: TestClient) -> None:
    album_id = client.post("/api/albums").json()["id"]

    resp = client.post(
        f"/api/albums/{album_id}/images",
        files=[
            ("files", ("a.jpg", _jpeg("red"), "image/jpeg")),
            ("files", ("b.jpg", _jpeg("blue"), "image/jpeg")),
            ("files", ("notiz.txt", b"hallo", "text/plain")),
        ],
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["added"]) == 2
    assert body["errors"][0]["filename"] == "notiz.txt"

    image_id = body["added"][0]["id"]
    thumb = client.get(f"/api/albums/{album_id}/images/{image_id}/thumb")
    assert thumb.status_code == 200
    assert thumb.headers["content-type"] == "image/webp"

    assert client.post(f"/api/albums/{album_id}/classify").json()["total"] == 2

    for _ in range(50):
        album = client.get(f"/api/albums/{album_id}").json()
        if album["job"]["status"] == "done":
            break
        time.sleep(0.05)
    assert album["job"] == {"status": "done", "done": 2, "total": 2}
    assert all(img["classification"]["category"] == "strand" for img in album["images"])

    pdf = client.get(f"/api/albums/{album_id}/export.pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")


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
