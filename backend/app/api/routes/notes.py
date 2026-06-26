"""Notes router (Track D · Notes, Phase 5).

Near-independent CRUD: save a chat answer / Studio output as a note, plus manual
notes. The NoteRepository already implements persistence; this module just
wires thin HTTP handlers on top of it.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    assert_notebook_owner,
    get_current_user,
    get_note_repo,
    get_notebook_repo,
)
from app.domain.models import Note, NoteCreate, NoteUpdate, User
from app.domain.ports.repositories import NoteRepository, NotebookRepository

router = APIRouter(prefix="/api", tags=["notes"])


@router.post(
    "/notebooks/{notebook_id}/notes",
    response_model=Note,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    notebook_id: uuid.UUID,
    body: NoteCreate,
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    repo: NoteRepository = Depends(get_note_repo),
    user: User = Depends(get_current_user),
) -> Note:
    assert_notebook_owner(notebook_repo, notebook_id, user)
    content = body.content
    if body.source_ref:
        # No dedicated column for source_ref; fold it into the note content as
        # a trailing pointer back to the originating message/output.
        content = f"{content}\n\n[source: {body.source_ref}]" if content else f"[source: {body.source_ref}]"
    return repo.create(
        notebook_id=notebook_id,
        title=body.title,
        content=content,
        origin=body.origin,
    )


@router.get("/notebooks/{notebook_id}/notes", response_model=list[Note])
def list_notes(
    notebook_id: uuid.UUID,
    repo: NoteRepository = Depends(get_note_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> list[Note]:
    assert_notebook_owner(notebook_repo, notebook_id, user)
    return repo.list_for_notebook(notebook_id)


@router.patch("/notes/{note_id}", response_model=Note)
def update_note(
    note_id: uuid.UUID,
    body: NoteUpdate,
    repo: NoteRepository = Depends(get_note_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> Note:
    existing = repo.get(note_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    assert_notebook_owner(notebook_repo, existing.notebook_id, user)
    note = repo.update(note_id, title=body.title, content=body.content)
    if not note:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return note


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: uuid.UUID,
    repo: NoteRepository = Depends(get_note_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> None:
    existing = repo.get(note_id)
    if not existing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    assert_notebook_owner(notebook_repo, existing.notebook_id, user)
    repo.delete(note_id)
