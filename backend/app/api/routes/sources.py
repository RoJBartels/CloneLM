"""Sources router (Track A · Ingestion, Phase 1).

``add_source`` accepts multipart/form-data (so file uploads and paste/url
share one endpoint) and runs the full parse -> chunk -> embed -> persist
pipeline inline within the request via ``IngestionService``.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import (
    assert_notebook_owner,
    get_chunk_repo,
    get_current_user,
    get_notebook_repo,
    get_source_repo,
    get_user_embedder,
)
from app.config import get_settings
from app.domain.models import Source, SourceType, User
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.repositories import ChunkRepository, NotebookRepository, SourceRepository
from app.services.ingestion.service import IngestionService
from app.shared.errors import UnsupportedSourceError, ValidationError

router = APIRouter(prefix="/api", tags=["sources"])


@router.post(
    "/notebooks/{notebook_id}/sources",
    response_model=Source,
    status_code=status.HTTP_201_CREATED,
)
async def add_source(
    notebook_id: uuid.UUID,
    type: SourceType = Form(...),
    title: str | None = Form(None),
    content: str | None = Form(None),
    url: str | None = Form(None),
    file: UploadFile | None = File(None),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    source_repo: SourceRepository = Depends(get_source_repo),
    chunk_repo: ChunkRepository = Depends(get_chunk_repo),
    embedder: EmbeddingProvider = Depends(get_user_embedder),
    user: User = Depends(get_current_user),
) -> Source:
    """Add a source (file/paste/url) and ingest it inline: parse -> chunk ->
    embed -> persist. Returns the Source with status=ready or status=error
    (parse/embed failures do not 500 — they surface via the status field)."""
    assert_notebook_owner(notebook_repo, notebook_id, user)

    file_bytes: bytes | None = None
    filename: str | None = None
    if type == SourceType.file:
        if file is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "`file` is required for type=file")
        filename = file.filename
        file_bytes = await file.read()

    settings = get_settings()
    service = IngestionService(
        source_repo=source_repo,
        chunk_repo=chunk_repo,
        embedder=embedder,
        chunk_tokens=settings.chunk_tokens,
        chunk_overlap=settings.chunk_overlap,
        chunk_strategy=settings.chunk_strategy,
    )
    try:
        return service.add_source(
            notebook_id=notebook_id,
            type=type,
            title=title,
            content=content,
            url=url,
            filename=filename,
            file_bytes=file_bytes,
        )
    except UnsupportedSourceError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc


@router.get("/notebooks/{notebook_id}/sources", response_model=list[Source])
def list_sources(
    notebook_id: uuid.UUID,
    repo: SourceRepository = Depends(get_source_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> list[Source]:
    assert_notebook_owner(notebook_repo, notebook_id, user)
    return repo.list_for_notebook(notebook_id)


@router.get("/sources/{source_id}", response_model=Source)
def get_source(
    source_id: uuid.UUID,
    repo: SourceRepository = Depends(get_source_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> Source:
    src = repo.get(source_id)
    if not src:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    assert_notebook_owner(notebook_repo, src.notebook_id, user)
    return src


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: uuid.UUID,
    repo: SourceRepository = Depends(get_source_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> None:
    src = repo.get(source_id)
    if not src:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Source not found")
    assert_notebook_owner(notebook_repo, src.notebook_id, user)
    repo.delete(source_id)
