# CloneLM — a faithfulness-first NotebookLM clone

CloneLM is a [NotebookLM](https://notebooklm.google.com)-style research assistant.
You create a **notebook**, add **sources** (PDF · text · Markdown · URL · pasted
text), and work with them: **grounded chat with clickable citations**, one-click
**Studio artifacts** (summary · FAQ · study guide · briefing · timeline), saved
**notes**, and a stretch **audio overview**. The UI is in German.

> ### North star — faithfulness over everything
> Every answer and artifact is produced **only** from retrieved chunks of the
> active notebook's sources (RAG), carries a **citation** you can click to see the
> exact supporting passage, and the system **refuses** when the sources don't
> support an answer — it never falls back on the model's world knowledge.
> Faithfulness here is **architectural** (RAG + mandatory citations + refusal),
> not a function of model size. See [CLAUDE.md](CLAUDE.md) for the hard invariants
> and [PLAN.md](PLAN.md) for the phase-by-phase build log.

It is demonstrably faithful — proven two ways:
- **Offline, in CI:** `backend/tests/test_faithfulness_eval.py` (deterministic, no key).
- **Live, real providers:** `backend/scripts/faithfulness_demo.py` ingests two
  sample sources and checks that supported questions are answered+cited while
  unsupported ones are refused.

---

## Architecture — modular monolith, hexagonal (ports & adapters)

```
  React (TS) SPA ──HTTP / SSE──▶  FastAPI  ──▶  Postgres + pgvector
                                    │
   api/      thin routers ─────────▶│  validate, call a service, return
   services/ use cases ────────────▶│  ingestion · retrieval · chat · studio · notes · audio
   domain/   entities + PORTS ◀─────┘  LLMProvider · EmbeddingProvider · TTSProvider ·
                ▲                       VectorStore · repositories   (no I/O, no SDKs)
   infrastructure/ adapters ──────────┘  anthropic_llm · bge_embeddings · pgvector_store ·
                                          SQLAlchemy repos · alembic · fake_* providers
```

**Dependency rule (enforced):** dependencies point inward.
`api → services → domain (ports)`; `infrastructure` implements those ports.
`services/` import **only** `domain/ports` — never `infrastructure/`, never a
vendor SDK. The composition root (`config.py` + `api/deps.py`) is the *only* place
that binds a port to a concrete adapter, chosen from env config.

**Pluggable providers** (swap = config change, not code change):

| Port | Default adapter | Alternatives |
|---|---|---|
| `LLMProvider` | Anthropic **Claude Haiku 4.5** (chat); **Sonnet 4.6** for Studio/Audio synthesis | `fake` (deterministic, offline); Sonnet/others by config |
| `EmbeddingProvider` | **bge-m3**, run locally (1024-dim, strong multilingual incl. German) | `fake` (offline); a SaaS embedder behind the same port |
| `TTSProvider` | **Piper** local neural TTS (two German voices for the two-host Audio Overview, run offline) | `fake` (valid silent WAV); a SaaS TTS behind the same port |
| `VectorStore` | pgvector cosine KNN, **notebook-scoped** | — |

No vendor SDK is imported outside its adapter. With `LLM_PROVIDER=fake` /
`EMBEDDING_PROVIDER=fake` the **entire app and test suite run with no API key and
no model download**.

### The faithfulness loop (shared by chat and Studio)
`question → retrieve top-k chunks (this notebook only) → numbered grounding prompt
with strict "only use sources / cite / refuse" rules → LLM structured output
(answer + per-claim citation markers) → map markers back to source chunks + char
spans → refuse if retrieval is empty/weak or the answer has no usable citations`.
This lives once in `services/chat/grounding.py` (`GroundedGenerator`) and is reused
by Studio and Audio.

### Data model
`notebook · source · chunk(embedding vector, char offsets, page) · conversation ·
message · citation(message|studio, denormalized source span) · note ·
studio_output · audio_overview`. The whole schema is one Alembic migration
(`backend/app/infrastructure/migrations/versions/0001_initial.py`); sources stamp
`embedding_model` / `chunk_strategy` so a future re-index can migrate cleanly.

---

## Quick start

Prerequisites: **Docker**, [**uv**](https://docs.astral.sh/uv/), **Node 20+**.

```bash
# 1. Config — copy the template and (optionally) add your Anthropic key
cp .env.example backend/.env        # set ANTHROPIC_API_KEY for real chat/Studio

# 2. Database (Postgres + pgvector)
docker compose up -d

# 3. Backend
cd backend
uv sync --extra embeddings --extra audio   # core deps + local bge-m3 (torch) +
                                    #   Piper neural TTS. Omit --extra embeddings to run
                                    #   EMBEDDING_PROVIDER=fake; omit --extra audio to run
                                    #   TTS_PROVIDER=fake (Audio Overview becomes silent).
uv run --extra audio python scripts/download_piper_voices.py   # one-time voice download
                                    #   (else they auto-download on the first audio request)
uv run alembic upgrade head         # create the schema
uv run uvicorn app.main:app --reload
#   → http://localhost:8000/health   ·   OpenAPI/docs at /docs

# 4. Frontend
cd ../frontend
npm install
npm run dev                         # → http://localhost:5173 (proxies /api + /health)
```

**No API key?** Set `LLM_PROVIDER=fake` (and `EMBEDDING_PROVIDER=fake` to skip the
~2 GB model download) in `backend/.env` to run the full UI loop against
deterministic fakes. Real grounded answers require `ANTHROPIC_API_KEY`.

The default real model is `claude-haiku-4-5`; Studio/Audio synthesis uses
`claude-sonnet-4-6` (`LLM_MODEL_HEAVY`). All model ids / providers / tuning live
in env (see `.env.example`).

---

## Tests & the faithfulness eval

```bash
cd backend
uv run pytest -q                              # full suite (DB up; uses fakes — offline)
uv run pytest tests/test_faithfulness_eval.py -q   # the north-star eval (CI-safe)
uv run ruff check app tests                   # lint

# Live, real-provider faithfulness demo (needs ANTHROPIC_API_KEY + bge-m3):
uv run --extra embeddings python scripts/faithfulness_demo.py
```

The live demo prints a PASS/FAIL table: supported questions → answered + cited;
unsupported questions → refused. Example (abridged):

```
[PASS] (supported→cite)   Welche Icon-Kategorien enthält das FontAwesome5-Paket?
       refused=False citations=1 — Das Paket enthält Brand logos, Tools…
       cite[1] FontAwesome5 Reference: “The package groups its icons into…”
[PASS] (unsupported→refuse) Wie hoch ist der Mount Everest?
       refused=True citations=0 — Die bereitgestellten Quellen enthalten keine…
Faithfulness eval: 4/4 passed
```

---

## Project layout

```
backend/
  app/
    main.py            app factory + router registration
    config.py          settings + provider selection (env-driven)
    api/               deps.py (composition root) · routes/ (notebooks, sources,
                       chat, studio, notes, audio, health)
    domain/            models.py (pure entities/DTOs) · ports/ (interfaces)
    services/          ingestion · retrieval · chat (GroundedGenerator) ·
                       studio · notes · audio
    infrastructure/    providers/ (anthropic_llm, bge_embeddings, fake_*, tts) ·
                       persistence/ (orm, repositories, pgvector_store, db) · migrations/
  tests/               contracts · per-feature tests · faithfulness eval (71 tests)
  scripts/             faithfulness_demo.py
  sample_data/         fontawesome5.md · photosynthesis.txt (for the demo)
frontend/              React + TS + Vite + Tailwind v4 (three-pane German UX)
design/                CloneLM-*.excalidraw (UI source of truth)
docker-compose.yml     Postgres + pgvector
```

---

## Design decisions

- **Faithfulness is architectural.** RAG is mandatory (never stuff whole sources),
  every claim cites a chunk, retrieval is strictly notebook-scoped, and refusal is
  a first-class path (empty/weak retrieval never reaches the LLM; an uncited answer
  is downgraded to a refusal). This is why a small, cheap model (Haiku 4.5) is the
  default — correctness comes from the pipeline, not model size.
- **Local embeddings (bge-m3).** Strong multilingual quality (the UI is German), no
  second SaaS vendor, no per-call cost — behind `EmbeddingProvider` so a hosted
  embedder is a config swap.
- **Two Claude tiers, one port.** Haiku 4.5 for chat; Sonnet 4.6 for heavier Studio
  /Audio synthesis — selected per task via the model override on the same
  `LLMProvider`, config-driven (`LLM_MODEL` / `LLM_MODEL_HEAVY`).
- **Modular monolith + hexagonal boundaries.** Feature modules update independently;
  ports/adapters let external tech update independently. This also let the build run
  as **parallel agent tracks** (one folder per track) against frozen Phase-0
  contracts — see PLAN.md.
- **Citations are denormalized** onto the citation row (source title + char span +
  snippet), so a citation still renders if a chunk is later re-indexed.

## Status

All product phases implemented (see [PLAN.md](PLAN.md)): notebooks, ingestion,
grounded cited chat with refusal (SSE), Studio artifacts, notes, and a stretch
audio overview. 71 backend tests pass; frontend builds; faithfulness verified
offline and live.
