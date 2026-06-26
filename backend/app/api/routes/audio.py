"""Audio Overview router (Track F · Audio, Phase 6 · STRETCH).

Generates a grounded two-host dialogue and renders it via the TTSProvider port.
Processing runs synchronously within the POST request (see
``app.services.audio.service.AudioService`` for why).
"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.api.deps import (
    assert_notebook_owner,
    get_audio_repo,
    get_current_user,
    get_notebook_repo,
    get_tts,
    get_user_embedder,
    get_user_llm,
    get_vector_store,
)
from app.domain.models import AudioOverview, User
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMProvider
from app.domain.ports.repositories import AudioRepository, NotebookRepository
from app.domain.ports.tts import TTSProvider
from app.domain.ports.vector_store import VectorStore
from app.services.audio.service import STORAGE_DIR, AudioService

router = APIRouter(prefix="/api", tags=["audio"])

_AUDIO_MEDIA_TYPES = {
    "wav": "audio/wav",
    "mp3": "audio/mpeg",
    "ogg": "audio/ogg",
}


@router.post(
    "/notebooks/{notebook_id}/audio",
    response_model=AudioOverview,
    status_code=status.HTTP_201_CREATED,
)
def generate_audio(
    notebook_id: uuid.UUID,
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    audio_repo: AudioRepository = Depends(get_audio_repo),
    vector_store: VectorStore = Depends(get_vector_store),
    embedder: EmbeddingProvider = Depends(get_user_embedder),
    llm: LLMProvider = Depends(get_user_llm),
    tts: TTSProvider = Depends(get_tts),
    user: User = Depends(get_current_user),
) -> AudioOverview:
    assert_notebook_owner(notebook_repo, notebook_id, user)

    service = AudioService(
        vector_store=vector_store,
        embedder=embedder,
        llm=llm,
        tts=tts,
        audio_repo=audio_repo,
    )
    return service.run(notebook_id)


@router.get("/notebooks/{notebook_id}/audio", response_model=list[AudioOverview])
def list_audio(
    notebook_id: uuid.UUID,
    repo: AudioRepository = Depends(get_audio_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    user: User = Depends(get_current_user),
) -> list[AudioOverview]:
    assert_notebook_owner(notebook_repo, notebook_id, user)
    return repo.list_for_notebook(notebook_id)


@router.get("/audio/{audio_id}/file")
def get_audio_file(
    audio_id: uuid.UUID,
    repo: AudioRepository = Depends(get_audio_repo),
    notebook_repo: NotebookRepository = Depends(get_notebook_repo),
    tts: TTSProvider = Depends(get_tts),
    user: User = Depends(get_current_user),
) -> FileResponse:
    audio = repo.get(audio_id)
    if audio is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audio overview not found.")
    assert_notebook_owner(notebook_repo, audio.notebook_id, user)

    file_path = os.path.join(STORAGE_DIR, f"{audio_id}.{tts.audio_format}")
    if not os.path.isfile(file_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audio file not found.")

    media_type = _AUDIO_MEDIA_TYPES.get(tts.audio_format, "application/octet-stream")
    return FileResponse(file_path, media_type=media_type)
