# CloneLM — a faithfulness-first NotebookLM clone

CloneLM is a [NotebookLM](https://notebooklm.google.com)-style research assistant.
You create a **notebook**, add **sources** (PDF / text / URL), and chat with them —
every answer is **grounded only in your sources**, carries **clickable citations**,
and the system **refuses** when the sources don't support an answer.

> **North star:** faithfulness. Answers come from retrieved source chunks (RAG),
> cite the exact passages, and never fall back on the model's world knowledge.
> See [CLAUDE.md](CLAUDE.md) for the hard invariants and [PLAN.md](PLAN.md) for the
> phase-by-phase implementation plan.

## Architecture (modular monolith, hexagonal boundaries)

```
React (TS) SPA ──HTTP/SSE──▶ FastAPI ──▶ Postgres + pgvector
                               │
   api/ (thin routers) ─▶ services/ (use cases) ─▶ domain/ (entities + PORTS)
                                                        ▲
                          infrastructure/ (adapters) ───┘  implements the ports
```

Dependencies point **inward**. `services/` import only `domain/ports`; vendor SDKs
(Anthropic, sentence-transformers…) live **only** inside `infrastructure/providers`.
The composition root (`config.py` + `api/deps.py`) is the single place that binds a
port to a concrete adapter, selected from env config.

- **LLM** → `LLMProvider` port. Default adapter: Anthropic **Claude Haiku 4.5**.
- **Embeddings** → `EmbeddingProvider` port. Default adapter: **bge-m3**, local.
- **Vectors** → pgvector. **TTS** → `TTSProvider` port (stretch).

## Quick start

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
# 1. Config
cp .env.example .env        # set ANTHROPIC_API_KEY for real chat (optional in dev)

# 2. Database (Postgres + pgvector)
docker compose up -d

# 3. Backend
cd backend
uv sync                     # core deps (fast; no ML libs)
uv run alembic upgrade head # create the schema
uv run uvicorn app.main:app --reload
#   → http://localhost:8000/health   ·   OpenAPI at /docs

# 4. Frontend
cd ../frontend
npm install
npm run dev                 # → http://localhost:5173
```

Without an `ANTHROPIC_API_KEY`, set `LLM_PROVIDER=fake` to run the full UI loop
against a deterministic fake LLM. The local embedding model is installed on demand
by the ingestion track: `uv sync --extra embeddings`.

## Status

Implemented phase by phase per [PLAN.md](PLAN.md). Phase 0 (contracts + infra) is
the foundation every feature track builds against.
