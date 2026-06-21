"""End-to-end ingestion via the HTTP API against live Postgres (skipped if the
DB isn't up). Uses the deterministic FakeEmbeddingProvider — never loads the
real bge-m3 model in tests."""
from __future__ import annotations

import io

from app.api.deps import get_embedder
from app.infrastructure.providers.fake_embeddings import FakeEmbeddingProvider


def _override_fake_embedder():
    return FakeEmbeddingProvider(dim=1024)


def test_add_paste_source_becomes_ready_with_chunks(client, db_available):
    client.app.dependency_overrides[get_embedder] = _override_fake_embedder
    try:
        nb = client.post("/api/notebooks", json={"title": "Ingestion Test"}).json()
        notebook_id = nb["id"]

        resp = client.post(
            f"/api/notebooks/{notebook_id}/sources",
            data={
                "type": "paste",
                "title": "Mein Text",
                "content": "Dies ist ein Testtext. " * 200,
            },
        )
        assert resp.status_code == 201, resp.text
        source = resp.json()
        assert source["status"] == "ready", source
        assert source["chunk_count"] > 0
        source_id = source["id"]

        got = client.get(f"/api/sources/{source_id}")
        assert got.status_code == 200
        assert got.json()["chunk_count"] == source["chunk_count"]

        listing = client.get(f"/api/notebooks/{notebook_id}/sources").json()
        assert any(s["id"] == source_id for s in listing)
    finally:
        client.app.dependency_overrides.pop(get_embedder, None)
        client.delete(f"/api/notebooks/{notebook_id}")


def test_add_source_missing_notebook_404(client, db_available):
    client.app.dependency_overrides[get_embedder] = _override_fake_embedder
    try:
        import uuid

        resp = client.post(
            f"/api/notebooks/{uuid.uuid4()}/sources",
            data={"type": "paste", "content": "hallo"},
        )
        assert resp.status_code == 404
    finally:
        client.app.dependency_overrides.pop(get_embedder, None)


def test_add_paste_source_missing_content_422(client, db_available):
    client.app.dependency_overrides[get_embedder] = _override_fake_embedder
    try:
        nb = client.post("/api/notebooks", json={"title": "Ingestion Test 2"}).json()
        notebook_id = nb["id"]
        resp = client.post(
            f"/api/notebooks/{notebook_id}/sources",
            data={"type": "paste"},
        )
        assert resp.status_code == 422
    finally:
        client.app.dependency_overrides.pop(get_embedder, None)
        client.delete(f"/api/notebooks/{notebook_id}")


def test_add_file_source_txt(client, db_available):
    client.app.dependency_overrides[get_embedder] = _override_fake_embedder
    try:
        nb = client.post("/api/notebooks", json={"title": "Ingestion Test File"}).json()
        notebook_id = nb["id"]

        file_content = ("Zeile eins.\nZeile zwei.\n" * 50).encode("utf-8")
        resp = client.post(
            f"/api/notebooks/{notebook_id}/sources",
            data={"type": "file"},
            files={"file": ("notes.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert resp.status_code == 201, resp.text
        source = resp.json()
        assert source["status"] == "ready"
        assert source["chunk_count"] > 0
        assert source["title"] == "notes.txt"
    finally:
        client.app.dependency_overrides.pop(get_embedder, None)
        client.delete(f"/api/notebooks/{notebook_id}")


def test_add_file_source_unsupported_type_rejected(client, db_available):
    client.app.dependency_overrides[get_embedder] = _override_fake_embedder
    try:
        nb = client.post("/api/notebooks", json={"title": "Ingestion Test Bad"}).json()
        notebook_id = nb["id"]

        resp = client.post(
            f"/api/notebooks/{notebook_id}/sources",
            data={"type": "file"},
            files={"file": ("evil.exe", io.BytesIO(b"\x00\x01\x02"), "application/octet-stream")},
        )
        assert resp.status_code == 422
    finally:
        client.app.dependency_overrides.pop(get_embedder, None)
        client.delete(f"/api/notebooks/{notebook_id}")
