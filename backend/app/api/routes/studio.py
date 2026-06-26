"""Studio router (Track E · Studio, Phase 4).

Generates grounded, cited artifacts (summary / faq / study_guide / briefing /
timeline) by reusing Track B's grounded-generation core (``GroundedGenerator``)
via ``StudioService``. Retrieval is scoped to the notebook (isolation) and uses
a broad top_k since Studio artifacts summarize the whole notebook, not a single
question; synthesis uses the heavier configured model.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    assert_notebook_owner,
    get_current_user,
    get_notebook_repo,
    get_studio_repo,
    get_user_embedder,
    get_user_llm,
    get_vector_store,
)
from app.config import get_settings
from app.domain.models import StudioOutput, StudioRequest, User
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMProvider
from app.domain.ports.repositories import NotebookRepository, StudioOutputRepository
from app.domain.ports.vector_store import VectorStore
from app.services.chat import GroundedGenerator
from app.services.studio import MIN_STUDIO_TOP_K, StudioService

router = APIRouter(prefix="/api", tags=["studio"])


@router.post(
    "/notebooks/{notebook_id}/studio",
    response_model=StudioOutput,
    status_code=status.HTTP_201_CREATED,
)
def generate_studio(
    notebook_id: uuid.UUID,
    body: StudioRequest,
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    studio_repo: StudioOutputRepository = Depends(get_studio_repo),
    vector_store: VectorStore = Depends(get_vector_store),
    embedder: EmbeddingProvider = Depends(get_user_embedder),
    llm: LLMProvider = Depends(get_user_llm),
    user: User = Depends(get_current_user),
) -> StudioOutput:
    assert_notebook_owner(notebook_repo, notebook_id, user)

    settings = get_settings()
    generator = GroundedGenerator(
        vector_store,
        embedder,
        llm,
        default_top_k=max(settings.retrieval_top_k, MIN_STUDIO_TOP_K),
        max_tokens=settings.studio_max_tokens,
    )
    service = StudioService(
        generator,
        studio_repo,
        heavy_model=settings.effective_heavy_model,
        top_k=max(settings.retrieval_top_k, MIN_STUDIO_TOP_K),
    )
    return service.generate(notebook_id=notebook_id, kind=body.kind)


@router.get("/notebooks/{notebook_id}/studio", response_model=list[StudioOutput])
def list_studio_outputs(
    notebook_id: uuid.UUID,
    repo: StudioOutputRepository = Depends(get_studio_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> list[StudioOutput]:
    assert_notebook_owner(notebook_repo, notebook_id, user)
    return repo.list_for_notebook(notebook_id)


@router.get("/studio/{output_id}", response_model=StudioOutput)
def get_studio_output(
    output_id: uuid.UUID,
    repo: StudioOutputRepository = Depends(get_studio_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> StudioOutput:
    out = repo.get(output_id)
    if not out:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Studio output not found")
    assert_notebook_owner(notebook_repo, out.notebook_id, user)
    return out
