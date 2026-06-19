# CLAUDE.md — Project Invariants

Hard rules for this project. These change only with a deliberate, major decision —
not in the course of normal implementation. For the evolving, phase-by-phase plan
see [PLAN.md](PLAN.md).

## What this is
A **NotebookLM clone** built as a hiring task. Reference: https://notebooklm.google.com
The evaluator is an AI-consulting company; they assess both engineering quality
**and** how we work (an agent session / Loom is part of the deliverable).

## North star — faithfulness over everything
The single most important property is **groundedness**: answers and generated
artifacts must come from the user's sources, be **traceable** to them, and the
system must **refuse / say so** when the sources don't support an answer.
Faithfulness is achieved through **architecture (RAG + citations + refusal)**,
**not** through picking a weak model.

## Non-negotiable invariants

1. **Grounded-only generation.** Every answer and Studio artifact is produced
   *only* from retrieved chunks of the **active notebook's** sources. The model
   must not answer from world/parametric knowledge. If the sources are
   insufficient, it must say so explicitly rather than guess.

2. **Mandatory citations.** Every factual claim carries a citation to the
   specific source chunk(s) it came from. The UI must let the user click a
   citation and see the exact supporting passage.

3. **RAG is required.** Never bypass retrieval by stuffing whole sources or
   relying on model memory. Generation is always conditioned on retrieved chunks.

4. **Notebook isolation.** Retrieval is scoped to a single notebook. No
   cross-notebook content may ever leak into an answer.

5. **Pluggable AI providers.** All text generation goes through an `LLMProvider`
   interface; all embeddings through an `EmbeddingProvider` interface. **No vendor
   SDK (Anthropic, etc.) is imported or called outside its provider adapter.**
   Swapping models/providers is a config change, not a code change.
   - Default LLM: **Claude Haiku 4.5** (`claude-haiku-4-5`).
   - Default embeddings: **bge-m3**, run locally.

6. **Config-driven models.** Model IDs, provider selection, and tuning live in
   config/env, never hardcoded in business logic.

7. **Fixed stack.** Backend: Python + FastAPI. Frontend: React + TypeScript.
   Data + vectors: Postgres + pgvector. Don't introduce a parallel stack without
   updating this file.

8. **Secrets via environment only.** Never commit API keys. The only required
   external key is the Anthropic key; embeddings run locally.

## Backend architecture (layers & structure)

Style: **modular monolith** with **hexagonal (ports & adapters)** boundaries
around everything external. Two decoupling axes — feature modules (so features
update independently) and ports/adapters (so external tech updates independently).

**Dependency rule (invariant):** dependencies point inward.
`api → services → domain (ports)`, and `infrastructure` implements those ports.
`services/` may import **only** `domain/ports` — never `infrastructure/` and never
a vendor SDK. The composition root (`api/deps.py` + `config.py`) is the *only*
place that binds a port to a concrete adapter, selected from env config.

```
  HTTP       api/            FastAPI routers — thin: validate, call, return
                │ depends on
  Use cases  services/       feature modules (orchestration):
                │               ingestion · retrieval · chat · studio · notes · audio
                │ depends ONLY on
  Core       domain/         entities + PORT interfaces (no I/O, no SDK):
                ▲               LLMProvider · EmbeddingProvider · TTSProvider ·
                │               VectorStore · ...Repository
                │ implements (adapters)
  Infra      infrastructure/ adapters: anthropic_llm · bge_embeddings · voyage… ·
                              SQLAlchemy models · repositories · pgvector_store · alembic

  Wiring: config.py + api/deps.py select which adapter implements each port.
```

### Planned file structure
```
backend/app/
  main.py                 # app factory, router registration
  config.py               # settings + provider selection (env-driven)
  api/
    deps.py               # composition root: binds ports -> adapters
    routes/               # notebooks, sources, chat, studio, notes, audio
  domain/
    models.py             # domain entities / schemas (pure)
    ports/                # llm.py, embeddings.py, tts.py, vector_store.py, repositories.py
  services/
    ingestion/  parsing/  chunking.py
    retrieval/
    chat/       prompts.py
    studio/     generators/   # summary, faq, study_guide, briefing, timeline
    notes/
    audio/      script.py
  infrastructure/
    providers/            # anthropic_llm, bge_embeddings, voyage_embeddings, tts_*
    persistence/          # db, orm models, repositories, pgvector_store
    migrations/           # alembic
  shared/                 # errors, logging, types
```

**Updatability note:** code boundaries make each box swappable in isolation. Two
changes are clean in code but require **re-processing data**: changing the
embedding model (re-embed + migrate vector dimension) or the chunking strategy
(re-chunk). Stamp `embedding_model` + `chunk_strategy` on each source and provide
a re-index job so old and new can coexist during migration.

## Anthropic / Claude usage notes (default provider)
- Use the official `anthropic` Python SDK, only inside the LLM provider adapter.
- Model id is exactly `claude-haiku-4-5` (200K context). Do not append date suffixes.
- Haiku 4.5 does **not** accept the `effort` parameter and is not part of the
  adaptive-thinking family — don't pass `thinking`/`effort` to it.
- Prefer **structured outputs** (`output_config.format`) for citation-bearing
  responses rather than assistant prefills.
- Stream responses for chat; set a sensible `max_tokens`.

## Definition of done (project level)
- Create a notebook, add sources (file/paste/URL), and chat with grounded,
  clickable citations.
- Studio outputs and saved notes work and are grounded.
- The app runs locally from documented steps (docker-compose for Postgres).
- Faithfulness behavior is demonstrable (correct refusal when unsupported).
