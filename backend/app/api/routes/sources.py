"""Sources router — CONTRACT STUB (Track A · Ingestion, Phase 1).

Publishes the endpoint shapes so the frontend and OpenAPI client are stable.
Track A implements parsing -> chunking -> embedding and the multipart file
upload variant. The repositories and EmbeddingProvider it needs already exist.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_source_repo
from app.domain.models import Source, SourceCreate
from app.domain.ports.repositories import SourceRepository

router = APIRouter(prefix="/api", tags=["sources"])

_TODO = "Not implemented yet — Track A (Ingestion, Phase 1)."


@router.post(
    "/notebooks/{notebook_id}/sources",
    response_model=Source,
    status_code=status.HTTP_201_CREATED,
)
def add_source(notebook_id: uuid.UUID, body: SourceCreate) -> Source:
    """Add a source (paste/url here; file upload arrives as multipart in Track A)."""
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _TODO)


@router.get("/notebooks/{notebook_id}/sources", response_model=list[Source])
def list_sources(
    notebook_id: uuid.UUID, repo: SourceRepository = Depends(get_source_repo)
) -> list[Source]:
    return repo.list_for_notebook(notebook_id)


@router.get("/sources/{source_id}", response_model=Source)
def get_source(
    source_id: uuid.UUID, repo: SourceRepository = Depends(get_source_repo)
) -> Source:
    src = repo.get(source_id)
    if not src:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    return src


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: uuid.UUID, repo: SourceRepository = Depends(get_source_repo)
) -> None:
    if not repo.delete(source_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
