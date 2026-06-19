"""End-to-end notebook CRUD against Postgres (skipped if the DB isn't up).
Exercises the full router -> repository -> ORM -> pgvector-enabled DB path."""
from __future__ import annotations


def test_notebook_lifecycle(client, db_available):
    # create
    resp = client.post("/api/notebooks", json={"title": "Mein Notebook"})
    assert resp.status_code == 201, resp.text
    nb = resp.json()
    assert nb["title"] == "Mein Notebook"
    assert nb["source_count"] == 0 and nb["note_count"] == 0
    nb_id = nb["id"]

    # list contains it
    listing = client.get("/api/notebooks").json()
    assert any(x["id"] == nb_id for x in listing)

    # get
    got = client.get(f"/api/notebooks/{nb_id}")
    assert got.status_code == 200
    assert got.json()["id"] == nb_id

    # update
    patched = client.patch(f"/api/notebooks/{nb_id}", json={"title": "Umbenannt"})
    assert patched.status_code == 200
    assert patched.json()["title"] == "Umbenannt"

    # sub-resource list endpoints are live and notebook-scoped (empty for now)
    assert client.get(f"/api/notebooks/{nb_id}/sources").json() == []
    assert client.get(f"/api/notebooks/{nb_id}/notes").json() == []
    assert client.get(f"/api/notebooks/{nb_id}/studio").json() == []

    # delete
    assert client.delete(f"/api/notebooks/{nb_id}").status_code == 204
    assert client.get(f"/api/notebooks/{nb_id}").status_code == 404


def test_create_notebook_default_title(client, db_available):
    resp = client.post("/api/notebooks", json={})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Unbenanntes Notebook"
    client.delete(f"/api/notebooks/{resp.json()['id']}")
