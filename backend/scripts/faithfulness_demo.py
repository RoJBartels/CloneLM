"""Live faithfulness demo / eval set (Phase 7).

Runs the REAL pipeline (bge-m3 embeddings + Claude via your .env) end to end and
checks the north star on a small eval set:

  * questions the loaded sources SUPPORT  -> a grounded answer WITH citations
  * questions they do NOT support         -> an explicit REFUSAL, no citations

It ingests the two bundled sample sources into one throwaway notebook, asks each
question through the same ``GroundedGenerator`` the API uses, prints a PASS/FAIL
table, deletes the notebook, and exits non-zero if any case fails.

Run it (DB up, real key in backend/.env, embeddings extra installed):

    cd backend
    docker compose up -d            # (from repo root) Postgres + pgvector
    uv run alembic upgrade head
    uv run --extra embeddings python scripts/faithfulness_demo.py

With LLM_PROVIDER=fake (or no key) the demo can't judge semantic grounding, so it
exits early with a notice — the deterministic, offline version of these checks is
``tests/test_faithfulness_eval.py`` (runs in CI without a key).
"""
from __future__ import annotations

import os
import sys

# Make `app` importable and load backend/.env regardless of where we're invoked.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_DIR)
os.chdir(_BACKEND_DIR)

from app.api import deps  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.domain.models import SourceType  # noqa: E402
from app.infrastructure.persistence.db import get_sessionmaker  # noqa: E402
from app.infrastructure.persistence.pgvector_store import PgVectorStore  # noqa: E402
from app.infrastructure.persistence.repositories import (  # noqa: E402
    SqlChunkRepository,
    SqlNotebookRepository,
    SqlSourceRepository,
)
from app.services.chat import GroundedGenerator  # noqa: E402
from app.services.ingestion.service import IngestionService  # noqa: E402

SAMPLES = [
    ("fontawesome5.md", "FontAwesome5 Reference"),
    ("photosynthesis.txt", "Photosynthesis Primer"),
]

# (question, must_be_supported). Two questions each source covers; two it doesn't.
EVAL_SET = [
    ("Welche Icon-Kategorien enthält das FontAwesome5-Paket?", True),
    ("Was geschieht während der lichtabhängigen Reaktionen der Photosynthese?", True),
    ("Wie hoch ist der Mount Everest?", False),
    ("Wer schrieb den Roman „Krieg und Frieden“?", False),
]


def main() -> int:
    settings = get_settings()
    embedder = deps.get_embedder()
    llm = deps.get_llm()

    if llm.model_id.startswith("fake"):
        print(
            "⚠  LLM_PROVIDER resolves to the fake LLM (no ANTHROPIC_API_KEY).\n"
            "   This demo needs a real model to judge semantic grounding.\n"
            "   Set ANTHROPIC_API_KEY in backend/.env, or run the offline eval:\n"
            "       uv run pytest tests/test_faithfulness_eval.py -q"
        )
        return 0

    print(f"LLM: {llm.model_id} | embeddings: {embedder.model_id} (dim {embedder.dim})\n")

    session = get_sessionmaker()()
    nb_repo = SqlNotebookRepository(session)
    notebook = nb_repo.create("Faithfulness Demo")
    print(f"notebook {notebook.id} — ingesting {len(SAMPLES)} sources…")

    ingestion = IngestionService(
        source_repo=SqlSourceRepository(session),
        chunk_repo=SqlChunkRepository(session),
        embedder=embedder,
        chunk_tokens=settings.chunk_tokens,
        chunk_overlap=settings.chunk_overlap,
        chunk_strategy=settings.chunk_strategy,
    )
    for filename, title in SAMPLES:
        path = os.path.join(_BACKEND_DIR, "sample_data", filename)
        with open(path, "rb") as fh:
            src = ingestion.add_source(
                notebook_id=notebook.id,
                type=SourceType.file,
                title=title,
                content=None,
                url=None,
                filename=filename,
                file_bytes=fh.read(),
            )
        print(f"  • {title}: {src.status.value} ({src.chunk_count} chunks)")

    generator = GroundedGenerator(
        PgVectorStore(session),
        embedder,
        llm,
        default_top_k=settings.retrieval_top_k,
        max_tokens=settings.llm_max_tokens,
    )

    print("\n" + "=" * 70)
    passed = 0
    try:
        for question, must_support in EVAL_SET:
            result = generator.generate(notebook_id=notebook.id, query=question)
            answered_and_cited = (not result.refused) and len(result.citations) > 0
            ok = answered_and_cited if must_support else result.refused
            passed += ok
            tag = "PASS" if ok else "FAIL"
            expect = "supported→cite" if must_support else "unsupported→refuse"
            print(f"[{tag}] ({expect}) {question}")
            print(
                f"       refused={result.refused} citations={len(result.citations)}"
                f" — {result.text[:130].strip()}"
            )
            if result.citations:
                c = result.citations[0]
                print(f"       cite[1] {c.source_title}: “{c.snippet[:90].strip()}”")
            print("-" * 70)
    finally:
        nb_repo.delete(notebook.id)  # tidy up the throwaway notebook
        session.close()

    total = len(EVAL_SET)
    print(f"\nFaithfulness eval: {passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
