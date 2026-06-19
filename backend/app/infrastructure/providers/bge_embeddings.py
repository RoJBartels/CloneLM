"""Local bge-m3 EmbeddingProvider (default).

The heavy ``sentence-transformers`` dependency is imported LAZILY (only when the
model is first used) and lives in the ``embeddings`` optional extra
(``uv sync --extra embeddings``). This keeps Phase 0 and the fake-provider path
free of torch, while the app still boots with this selected as the default.

Track A (ingestion) owns refinements (batching, sparse vectors, query prefix).
"""
from __future__ import annotations

from app.domain.ports.embeddings import EmbeddingProvider
from app.shared.logging import get_logger

log = get_logger(__name__)


class BgeM3EmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "BAAI/bge-m3", dim: int = 1024) -> None:
        self._model_name = model_name
        self._dim = dim
        self._model = None  # lazy

    @property
    def model_id(self) -> str:
        return self._model_name

    @property
    def dim(self) -> int:
        return self._dim

    def _ensure_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover - depends on extra
                raise RuntimeError(
                    "bge-m3 requires the 'embeddings' extra. Install it with "
                    "`uv sync --extra embeddings` or set EMBEDDING_PROVIDER=fake."
                ) from exc
            log.info("Loading embedding model %s (first use)…", self._model_name)
            self._model = SentenceTransformer(self._model_name)
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        vectors = model.encode(
            texts, normalize_embeddings=True, convert_to_numpy=True
        )
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]
