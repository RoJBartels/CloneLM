"""Studio router — CONTRACT STUB (Track E · Studio, Phase 4).

Generates grounded, cited artifacts (summary / faq / study_guide / briefing /
timeline) by reusing Track B's grounded-generation core. Implemented after that
core lands.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_studio_repo
from app.domain.models import StudioOutput, StudioRequest
from app.domain.ports.repositories import StudioOutputRepository

router = APIRouter(prefix="/api", tags=["studio"])

_TODO = "Not implemented yet — Track E (Studio, Phase 4)."


@router.post(
    "/notebooks/{notebook_id}/studio",
    response_model=StudioOutput,
    status_code=status.HTTP_201_CREATED,
)
def generate_studio(notebook_id: uuid.UUID, body: StudioRequest) -> StudioOutput:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _TODO)


@router.get("/notebooks/{notebook_id}/studio", response_model=list[StudioOutput])
def list_studio_outputs(
    notebook_id: uuid.UUID, repo: StudioOutputRepository = Depends(get_studio_repo)
) -> list[StudioOutput]:
    return repo.list_for_notebook(notebook_id)


@router.get("/studio/{output_id}", response_model=StudioOutput)
def get_studio_output(
    output_id: uuid.UUID, repo: StudioOutputRepository = Depends(get_studio_repo)
) -> StudioOutput:
    out = repo.get(output_id)
    if not out:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Studio output not found")
    return out
