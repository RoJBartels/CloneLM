"""Notes router — CONTRACT STUB (Track D · Notes, Phase 5).

Near-independent CRUD: save a chat answer / Studio output as a note, plus manual
notes. The NoteRepository already implements persistence; Track D wires these
handlers + UI. List/read are live now; create/update/delete are left to Track D
to keep the phase boundary crisp.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_note_repo
from app.domain.models import Note, NoteCreate, NoteUpdate
from app.domain.ports.repositories import NoteRepository

router = APIRouter(prefix="/api", tags=["notes"])

_TODO = "Not implemented yet — Track D (Notes, Phase 5)."


@router.post(
    "/notebooks/{notebook_id}/notes",
    response_model=Note,
    status_code=status.HTTP_201_CREATED,
)
def create_note(notebook_id: uuid.UUID, body: NoteCreate) -> Note:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _TODO)


@router.get("/notebooks/{notebook_id}/notes", response_model=list[Note])
def list_notes(
    notebook_id: uuid.UUID, repo: NoteRepository = Depends(get_note_repo)
) -> list[Note]:
    return repo.list_for_notebook(notebook_id)


@router.patch("/notes/{note_id}", response_model=Note)
def update_note(note_id: uuid.UUID, body: NoteUpdate) -> Note:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _TODO)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: uuid.UUID) -> None:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _TODO)
