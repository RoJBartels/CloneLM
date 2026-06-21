"""End-to-end notes CRUD against Postgres (skipped if the DB isn't up).
Exercises router -> NoteRepository -> ORM -> DB, plus notebook-scoping and 404s."""
from __future__ import annotations


def _make_notebook(client, title="Notes Test Notebook"):
    resp = client.post("/api/notebooks", json={"title": title})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def test_note_lifecycle_manual_origin(client, db_available):
    nb_id = _make_notebook(client)

    # create (manual origin, default)
    resp = client.post(
        f"/api/notebooks/{nb_id}/notes",
        json={"title": "My Note", "content": "Some content"},
    )
    assert resp.status_code == 201, resp.text
    note = resp.json()
    assert note["title"] == "My Note"
    assert note["content"] == "Some content"
    assert note["origin"] == "manual"
    assert note["notebook_id"] == nb_id
    note_id = note["id"]

    # list (notebook-scoped) contains it
    listing = client.get(f"/api/notebooks/{nb_id}/notes").json()
    assert any(n["id"] == note_id for n in listing)

    # update title only
    patched = client.patch(f"/api/notes/{note_id}", json={"title": "Renamed"})
    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == "Renamed"
    assert patched.json()["content"] == "Some content"

    # update content only
    patched2 = client.patch(f"/api/notes/{note_id}", json={"content": "New content"})
    assert patched2.status_code == 200
    assert patched2.json()["content"] == "New content"
    assert patched2.json()["title"] == "Renamed"

    # delete
    assert client.delete(f"/api/notes/{note_id}").status_code == 204

    # subsequent get via list no longer contains it
    listing_after = client.get(f"/api/notebooks/{nb_id}/notes").json()
    assert not any(n["id"] == note_id for n in listing_after)

    client.delete(f"/api/notebooks/{nb_id}")


def test_note_chat_origin_and_source_ref(client, db_available):
    nb_id = _make_notebook(client)

    resp = client.post(
        f"/api/notebooks/{nb_id}/notes",
        json={
            "title": "Saved answer",
            "content": "The answer was X.",
            "origin": "chat",
            "source_ref": "message:1234",
        },
    )
    assert resp.status_code == 201, resp.text
    note = resp.json()
    assert note["origin"] == "chat"
    # source_ref has no dedicated column; it's folded into content as a pointer.
    assert "message:1234" in note["content"]
    assert "The answer was X." in note["content"]

    client.delete(f"/api/notes/{note['id']}")
    client.delete(f"/api/notebooks/{nb_id}")


def test_notes_are_notebook_scoped(client, db_available):
    nb_a = _make_notebook(client, "Notebook A")
    nb_b = _make_notebook(client, "Notebook B")

    resp = client.post(
        f"/api/notebooks/{nb_a}/notes",
        json={"title": "Only in A", "content": "..."},
    )
    assert resp.status_code == 201
    note_id = resp.json()["id"]

    listing_a = client.get(f"/api/notebooks/{nb_a}/notes").json()
    listing_b = client.get(f"/api/notebooks/{nb_b}/notes").json()

    assert any(n["id"] == note_id for n in listing_a)
    assert not any(n["id"] == note_id for n in listing_b)

    client.delete(f"/api/notes/{note_id}")
    client.delete(f"/api/notebooks/{nb_a}")
    client.delete(f"/api/notebooks/{nb_b}")


def test_create_note_unknown_notebook_404(client, db_available):
    fake_id = "00000000-0000-0000-0000-000000000000"
    resp = client.post(
        f"/api/notebooks/{fake_id}/notes",
        json={"title": "Orphan", "content": "..."},
    )
    assert resp.status_code == 404


def test_update_and_delete_missing_note_404(client, db_available):
    fake_id = "00000000-0000-0000-0000-000000000000"

    patched = client.patch(f"/api/notes/{fake_id}", json={"title": "X"})
    assert patched.status_code == 404

    deleted = client.delete(f"/api/notes/{fake_id}")
    assert deleted.status_code == 404
