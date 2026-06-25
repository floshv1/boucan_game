"""Router tests for the pack CRUD/import/export endpoints (offline, TestClient)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.packs import router as packs_router


@pytest.fixture(autouse=True)
def _tmp_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("PACKS_DIR", str(tmp_path / "packs"))
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(packs_router, prefix="/api")
    return TestClient(app, raise_server_exceptions=False)


def test_create_list_get_delete_roundtrip(client):
    r = client.post("/api/packs", json={"name": "P", "mode": "qcm", "items": []})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert any(s["id"] == pid for s in client.get("/api/packs").json()["packs"])
    assert client.get(f"/api/packs/{pid}").json()["name"] == "P"
    assert client.delete(f"/api/packs/{pid}").json()["deleted"] is True
    assert client.get(f"/api/packs/{pid}").status_code == 404


def test_create_invalid_mode_returns_400(client):
    assert client.post("/api/packs", json={"name": "P", "mode": "nope", "items": []}).status_code == 400


def test_update_preserves_id(client):
    pid = client.post("/api/packs", json={"name": "P", "mode": "qcm", "items": []}).json()["id"]
    r = client.put(f"/api/packs/{pid}", json={"name": "P2", "mode": "qcm", "items": []})
    assert r.status_code == 200
    assert r.json()["id"] == pid
    assert client.get(f"/api/packs/{pid}").json()["name"] == "P2"


def test_update_missing_returns_404(client):
    assert client.put("/api/packs/nope", json={"name": "X", "mode": "qcm", "items": []}).status_code == 404


def test_export_sets_attachment_header(client):
    pid = client.post("/api/packs", json={"name": "Ma Soirée", "mode": "qcm", "items": []}).json()["id"]
    exported = client.get(f"/api/packs/{pid}/export")
    assert exported.status_code == 200
    assert "attachment" in exported.headers.get("content-disposition", "")
    assert exported.json()["name"] == "Ma Soirée"


def test_export_import_roundtrip_creates_new_id(client):
    pid = client.post(
        "/api/packs",
        json={"name": "P", "mode": "buzzer", "items": [{"question": "q", "answer": "a", "points": 1}]},
    ).json()["id"]
    exported = client.get(f"/api/packs/{pid}/export").json()
    imported = client.post("/api/packs/import", json=exported).json()
    assert imported["id"] != pid
    assert imported["items"][0]["answer"] == "a"


def test_media_upload_returns_url_and_writes_file(client, tmp_path):
    r = client.post("/api/media", files={"file": ("x.png", b"\x89PNG\r\n\x1a\nfake", "image/png")})
    assert r.status_code == 200
    url = r.json()["url"]
    assert url.startswith("/media/") and url.endswith(".png")
    name = url.rsplit("/", 1)[1]
    assert (tmp_path / "media" / name).read_bytes() == b"\x89PNG\r\n\x1a\nfake"


def test_media_rejects_non_image(client):
    r = client.post("/api/media", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400
