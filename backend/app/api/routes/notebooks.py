"""Notebooks router — full CRUD. Notebooks are foundational (not a feature
track), so this is implemented in Phase 0. Routers stay thin: validate, call
the repository (the persistence boundary), return."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_notebook_repo
from app.domain.models import Notebook, NotebookCreate, NotebookUpdate
from app.domain.ports.repositories import NotebookRepository

router = APIRouter(prefix="/api/notebooks", tags=["notebooks"])


@router.post("", response_model=Notebook, status_code=status.HTTP_201_CREATED)
def create_notebook(
    body: NotebookCreate, repo: NotebookRepository = Depends(get_notebook_repo)
) -> Notebook:
    return repo.create(title=body.title)


@router.get("", response_model=list[Notebook])
def list_notebooks(repo: NotebookRepository = Depends(get_notebook_repo)) -> list[Notebook]:
    return repo.list()


@router.get("/{notebook_id}", response_model=Notebook)
def get_notebook(
    notebook_id: uuid.UUID, repo: NotebookRepository = Depends(get_notebook_repo)
) -> Notebook:
    nb = repo.get(notebook_id)
    if not nb:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notebook not found")
    return nb


@router.patch("/{notebook_id}", response_model=Notebook)
def update_notebook(
    notebook_id: uuid.UUID,
    body: NotebookUpdate,
    repo: NotebookRepository = Depends(get_notebook_repo),
) -> Notebook:
    nb = repo.update(notebook_id, title=body.title)
    if not nb:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notebook not found")
    return nb


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook(
    notebook_id: uuid.UUID, repo: NotebookRepository = Depends(get_notebook_repo)
) -> None:
    if not repo.delete(notebook_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notebook not found")
