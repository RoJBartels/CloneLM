"""Notebooks router — full CRUD, scoped to the current user. Notebooks are the
ownership anchor: every other resource hangs off a notebook, so authorization
everywhere reduces to "does this user own the notebook?". Localhost resolves to
the single seeded local user, so behaviour there is unchanged."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import assert_notebook_owner, get_current_user, get_notebook_repo
from app.domain.models import Notebook, NotebookCreate, NotebookUpdate, User
from app.domain.ports.repositories import NotebookRepository

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


@router.post("", response_model=Notebook, status_code=status.HTTP_201_CREATED)
def create_notebook(
    body: NotebookCreate,
    repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> Notebook:
    return repo.create(body.title, user_id=user.id)


@router.get("", response_model=list[Notebook])
def list_notebooks(
    repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> list[Notebook]:
    return repo.list_for_user(user.id)


@router.get("/{notebook_id}", response_model=Notebook)
def get_notebook(
    notebook_id: uuid.UUID,
    repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> Notebook:
    assert_notebook_owner(repo, notebook_id, user)
    nb = repo.get(notebook_id)
    if not nb:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notebook not found")
    return nb


@router.patch("/{notebook_id}", response_model=Notebook)
def update_notebook(
    notebook_id: uuid.UUID,
    body: NotebookUpdate,
    repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> Notebook:
    assert_notebook_owner(repo, notebook_id, user)
    nb = repo.update(notebook_id, title=body.title)
    if not nb:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notebook not found")
    return nb


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook(
    notebook_id: uuid.UUID,
    repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> None:
    assert_notebook_owner(repo, notebook_id, user)
    if not repo.delete(notebook_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notebook not found")
