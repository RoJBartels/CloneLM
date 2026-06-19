"""Audio Overview router — CONTRACT STUB (Track F · Audio, Phase 6 · STRETCH).

Generates a grounded two-host dialogue and renders it via the TTSProvider port.
Deferrable; the fake TTS adapter already exists for the loop.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_audio_repo
from app.domain.models import AudioOverview
from app.domain.ports.repositories import AudioRepository

router = APIRouter(prefix="/api", tags=["audio"])

_TODO = "Not implemented yet — Track F (Audio Overview, Phase 6, stretch)."


@router.post(
    "/notebooks/{notebook_id}/audio",
    response_model=AudioOverview,
    status_code=status.HTTP_201_CREATED,
)
def generate_audio(notebook_id: uuid.UUID) -> AudioOverview:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, _TODO)


@router.get("/notebooks/{notebook_id}/audio", response_model=list[AudioOverview])
def list_audio(
    notebook_id: uuid.UUID, repo: AudioRepository = Depends(get_audio_repo)
) -> list[AudioOverview]:
    return repo.list_for_notebook(notebook_id)
