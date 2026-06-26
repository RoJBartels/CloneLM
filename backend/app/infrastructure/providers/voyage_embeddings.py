"""Hosted Voyage AI EmbeddingProvider (used in the deployed build).

Voyage AI is an Anthropic company, but its embeddings are a separate API with
their OWN key (``VOYAGE_API_KEY``) — they are NOT served through the Anthropic
key. This adapter is the only place the ``voyageai`` SDK is imported, per the
ports/adapters rule.

Why this exists: a hosted deploy (Railway) has no GPU and we don't want to ship
the heavy local bge-m3 stack (torch/sentence-transformers). voyage-3.5 returns
1024-dim vectors by default — the same dimension as bge-m3 — so the pgvector
column and schema are unchanged; only the model that fills them differs.

The ``voyageai`` dependency is imported LAZILY so the rest of the app (and the
fake/bge paths) boots without it installed.
"""
from __future__ import annotations

from app.domain.ports.embeddings import EmbeddingProvider
from app.shared.logging import get_logger

log = get_logger(__name__)

# Voyage caps a single request at 1000 inputs (and a per-request token budget).
# A long PDF can produce hundreds of chunks, so embed in batches well under that.
_BATCH_SIZE = 128


class VoyageEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self, *, api_key: str, model: str = "voyage-3.5", dim: int = 1024
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._dim = dim
        self._client = None  # lazy

    @property
    def model_id(self) -> str:
        return self._model

    @property
    def dim(self) -> int:
        return self._dim

    def _ensure_client(self):
        if self._client is None:
            try:
                import voyageai
            except ImportError as exc:  # pragma: no cover - depends on the dep
                raise RuntimeError(
                    "Voyage embeddings require the 'voyageai' package. Install it "
                    "with `uv sync` (it is a default dependency) or set DEPLOYED=false."
                ) from exc
            log.info("Initializing Voyage AI client (model %s)", self._model)
            self._client = voyageai.Client(api_key=self._api_key)
        return self._client

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        client = self._ensure_client()
        out: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start : start + _BATCH_SIZE]
            result = client.embed(
                batch,
                model=self._model,
                input_type=input_type,
                output_dimension=self._dim,
            )
            out.extend(result.embeddings)
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # input_type="document" / "query" is Voyage's retrieval asymmetry: it
        # tunes the two sides of the vector space against each other.
        return self._embed(texts, input_type="document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="query")[0]
