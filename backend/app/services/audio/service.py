"""AudioService — orchestrates the Audio Overview generation loop.

create AudioOverview row (processing) -> build grounded script -> synthesize
via TTSProvider -> write the file to disk -> mark ready (or error).

Processing runs SYNCHRONOUSLY within the request. The fake TTS adapter is
instant and the script generation (one grounded LLM call) takes a few seconds
at most for this take-home, so a background task isn't worth the added
complexity (the client would otherwise have to poll the GET endpoint for a
status flip with no real latency win in this fake-TTS setup). This is
documented here for anyone swapping in a slow real TTS vendor later — at that
point switching this call to FastAPI ``BackgroundTasks`` is a one-line change
at the call site in the route, since ``AudioService.run`` already takes no
request-scoped state beyond its constructor args.
"""
from __future__ import annotations

import os
import uuid

from app.domain.models import AudioOverview, AudioStatus
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.llm import LLMProvider
from app.domain.ports.repositories import AudioRepository
from app.domain.ports.tts import TTSProvider
from app.domain.ports.vector_store import VectorStore

from .script import build_script

# Anchored to the `backend/` package root (not the process CWD) so the storage
# location is stable regardless of where uvicorn/pytest is invoked from.
_BACKEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
STORAGE_DIR = os.path.join(_BACKEND_ROOT, "storage", "audio")


class AudioService:
    def __init__(
        self,
        *,
        vector_store: VectorStore,
        embedder: EmbeddingProvider,
        llm: LLMProvider,
        tts: TTSProvider,
        audio_repo: AudioRepository,
    ) -> None:
        self._vector_store = vector_store
        self._embedder = embedder
        self._llm = llm
        self._tts = tts
        self._audio_repo = audio_repo

    def run(self, notebook_id: uuid.UUID) -> AudioOverview:
        """Generate one Audio Overview for ``notebook_id`` and return its
        final (ready or error) state."""
        audio = self._audio_repo.create(notebook_id)

        try:
            segments, result = build_script(
                notebook_id=notebook_id,
                vector_store=self._vector_store,
                embedder=self._embedder,
                llm=self._llm,
            )

            # Sources insufficient: the generator refused. We still render the
            # short, honest "insufficient sources" admission the script asked
            # for as a spoken note (so the user gets audible feedback) rather
            # than silently erroring — but only if we actually got speakable
            # segments back. If parsing produced nothing at all, mark error.
            if result.refused and not segments:
                self._audio_repo.set_status(audio.id, AudioStatus.error)
                return self._require(audio.id)

            if not segments:
                self._audio_repo.set_status(audio.id, AudioStatus.error)
                return self._require(audio.id)

            audio_bytes = self._tts.synthesize(segments)

            os.makedirs(STORAGE_DIR, exist_ok=True)
            file_path = os.path.join(
                STORAGE_DIR, f"{audio.id}.{self._tts.audio_format}"
            )
            with open(file_path, "wb") as f:
                f.write(audio_bytes)

            url = f"/api/audio/{audio.id}/file"
            self._audio_repo.set_status(audio.id, AudioStatus.ready, url=url)
            return self._require(audio.id)
        except Exception:
            self._audio_repo.set_status(audio.id, AudioStatus.error)
            return self._require(audio.id)

    def _require(self, audio_id: uuid.UUID) -> AudioOverview:
        audio = self._audio_repo.get(audio_id)
        assert audio is not None  # we just created/updated it in this request
        return audio
