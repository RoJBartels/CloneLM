"""Retrieval tests (Track B, Phase 2).

Verify the retrieval service against real Postgres + pgvector:
  - notebook-scoped retrieval returns the most-similar chunks, and
  - cross-notebook isolation (invariant #4): chunks from notebook B are never
    returned for notebook A.

Uses the deterministic FakeEmbeddingProvider (identical text -> identical
vector), so embedding a query equal to a chunk's text makes that chunk the top
match.
"""
from __future__ import annotations

import uuid

import pytest

from app.infrastructure.persistence import orm
from app.infrastructure.persistence.db import get_sessionmaker
from app.infrastructure.persistence.pgvector_store import PgVectorStore
from app.infrastructure.providers.fake_embeddings import FakeEmbeddingProvider
from app.services.retrieval import Retriever

EMBED_DIM = 1024


@pytest.fixture
def session(db_available):
    s = get_sessionmaker()()
    try:
        yield s
    finally:
        s.rollback()
        s.close()


def _seed_notebook_with_chunks(
    session, embedder: FakeEmbeddingProvider, *, title: str, texts: list[str]
) -> tuple[uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    """Create a notebook + one ready source + embedded chunks. Returns ids."""
    notebook = orm.NotebookORM(title=title)
    session.add(notebook)
    session.flush()

    source = orm.SourceORM(
        notebook_id=notebook.id,
        type="paste",
        title=f"{title} source",
        status="ready",
    )
    session.add(source)
    session.flush()

    chunk_ids: list[uuid.UUID] = []
    for i, text in enumerate(texts):
        emb = embedder.embed_documents([text])[0]
        chunk = orm.ChunkORM(
            source_id=source.id,
            notebook_id=notebook.id,
            ordinal=i,
            text=text,
            token_count=len(text.split()),
            start_char=0,
            end_char=len(text),
            embedding=emb,
            embedding_model=embedder.model_id,
        )
        session.add(chunk)
        session.flush()
        chunk_ids.append(chunk.id)

    session.commit()
    return notebook.id, source.id, chunk_ids


def test_retrieval_returns_notebook_scoped_chunks(session):
    embedder = FakeEmbeddingProvider(dim=EMBED_DIM)
    uniq = uuid.uuid4().hex[:8]
    target = f"Photosynthesis converts light into chemical energy {uniq}"
    other = f"The capital of France is Paris {uniq}"

    nb_id, _src, chunk_ids = _seed_notebook_with_chunks(
        session, embedder, title=f"NB-{uniq}", texts=[target, other]
    )

    retriever = Retriever(PgVectorStore(session), embedder)
    results = retriever.retrieve(notebook_id=nb_id, query=target, top_k=8)

    assert results, "expected at least one chunk"
    # The chunk whose text equals the query is the closest match.
    assert results[0].text == target
    assert results[0].chunk_id in chunk_ids
    assert results[0].source_title == f"NB-{uniq} source"
    # cosine similarity of identical vectors ~= 1.0
    assert results[0].score == pytest.approx(1.0, abs=1e-3)


def test_cross_notebook_isolation(session):
    """A chunk in notebook B must NEVER be returned when querying notebook A."""
    embedder = FakeEmbeddingProvider(dim=EMBED_DIM)
    uniq = uuid.uuid4().hex[:8]
    shared_text = f"Confidential financials for project orion {uniq}"

    nb_a, _sa, _ca = _seed_notebook_with_chunks(
        session, embedder, title=f"A-{uniq}", texts=[f"alpha note {uniq}"]
    )
    nb_b, _sb, chunks_b = _seed_notebook_with_chunks(
        session, embedder, title=f"B-{uniq}", texts=[shared_text]
    )

    retriever = Retriever(PgVectorStore(session), embedder)

    # Query notebook A with text that exactly matches a chunk in notebook B.
    results_a = retriever.retrieve(notebook_id=nb_a, query=shared_text, top_k=8)
    returned_ids = {r.chunk_id for r in results_a}
    assert not (returned_ids & set(chunks_b)), "notebook B chunk leaked into A"
    for r in results_a:
        assert r.source_id != _sb

    # Sanity: the same query DOES find the chunk when scoped to notebook B.
    results_b = retriever.retrieve(notebook_id=nb_b, query=shared_text, top_k=8)
    assert chunks_b[0] in {r.chunk_id for r in results_b}


def test_source_filter_restricts_results(session):
    embedder = FakeEmbeddingProvider(dim=EMBED_DIM)
    uniq = uuid.uuid4().hex[:8]

    notebook = orm.NotebookORM(title=f"Filter-{uniq}")
    session.add(notebook)
    session.flush()

    src1 = orm.SourceORM(
        notebook_id=notebook.id, type="paste", title="s1", status="ready"
    )
    src2 = orm.SourceORM(
        notebook_id=notebook.id, type="paste", title="s2", status="ready"
    )
    session.add_all([src1, src2])
    session.flush()

    text1 = f"selectable source one content {uniq}"
    text2 = f"selectable source two content {uniq}"
    c1 = orm.ChunkORM(
        source_id=src1.id, notebook_id=notebook.id, ordinal=0, text=text1,
        start_char=0, end_char=len(text1),
        embedding=embedder.embed_documents([text1])[0],
        embedding_model=embedder.model_id,
    )
    c2 = orm.ChunkORM(
        source_id=src2.id, notebook_id=notebook.id, ordinal=0, text=text2,
        start_char=0, end_char=len(text2),
        embedding=embedder.embed_documents([text2])[0],
        embedding_model=embedder.model_id,
    )
    session.add_all([c1, c2])
    session.commit()

    retriever = Retriever(PgVectorStore(session), embedder)
    results = retriever.retrieve(
        notebook_id=notebook.id, query=text2, top_k=8, source_ids=[src1.id]
    )
    returned_sources = {r.source_id for r in results}
    assert returned_sources <= {src1.id}
    assert src2.id not in returned_sources


def test_empty_query_returns_nothing(session):
    embedder = FakeEmbeddingProvider(dim=EMBED_DIM)
    nb_id, _src, _chunks = _seed_notebook_with_chunks(
        session, embedder, title=f"E-{uuid.uuid4().hex[:8]}", texts=["something"]
    )
    retriever = Retriever(PgVectorStore(session), embedder)
    assert retriever.retrieve(notebook_id=nb_id, query="   ", top_k=8) == []
