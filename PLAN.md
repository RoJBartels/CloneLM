# PLAN.md — NotebookLM Clone

Living implementation plan. Updated as the project proceeds. Hard rules that
should *not* drift live in [CLAUDE.md](CLAUDE.md).

**Status legend:** ☐ not started · ◐ in progress · ☑ done

---

## Architecture overview

```
React (TS) SPA  ──HTTP/SSE──>  FastAPI backend  ──>  Postgres + pgvector
                                   │
                                   ├─ Ingestion: parse → chunk → embed (bge-m3 local)
                                   ├─ Retrieval: vector search (scoped to notebook)
                                   ├─ LLMProvider (default: Claude Haiku 4.5)
                                   └─ EmbeddingProvider (default: bge-m3 local)
```

**Faithfulness pipeline (the core loop):**
`question → retrieve top-k chunks (this notebook) → grounded prompt with numbered
chunks → LLM answers citing chunk ids → map citations to source spans → render
with click-through → (stretch) groundedness check`.

### Provider abstractions (build in Phase 0, never bypass)
- `EmbeddingProvider`: `embed(texts) -> vectors`, `dim`, `model_id`.
  Adapters: `BgeM3Local` (default), `Voyage` (documented fallback).
- `LLMProvider`: `complete(messages, **opts)`, `stream(...)`, `model_id`.
  Adapters: `Anthropic` (default, Haiku 4.5). Documented alternatives: Sonnet 4.6,
  Qwen3-via-Fireworks, Cohere.

### Data model (initial)
- `notebook(id, title, created_at)`
- `source(id, notebook_id, type[file|paste|url], title, uri, status, created_at)`
- `chunk(id, source_id, notebook_id, ordinal, text, token_count, embedding vector, metadata)`
- `conversation(id, notebook_id, created_at)`
- `message(id, conversation_id, role, content, created_at)`
- `citation(id, message_id, chunk_id, start_char, end_char)`
- `note(id, notebook_id, title, content, origin[chat|studio|manual], created_at)`
- `studio_output(id, notebook_id, kind, content, created_at)`

---

## Execution strategy — parallel tracks (multi-agent)

Phases are listed sequentially for clarity, but most run **concurrently** once the
shared contracts exist. The plan is built so several agents can work at once with
minimal collision.

**Contracts first, then fan out.** The only true bottleneck is the contract layer
(Phase 0a): the data model + first migration, the `domain/ports` interfaces, the
composition-root wiring, and the HTTP/OpenAPI shape. Land that with **one** agent;
everything downstream then builds against those contracts (and against fakes)
instead of waiting on each other.

**Dependency graph**
```
        ┌────────────── Phase 0a: CONTRACTS (gate, 1 agent) ──────────────┐
        │  data model + migration · ports · deps wiring · API/OpenAPI shape │
        └────┬──────────┬──────────┬──────────┬───────────────────────────┘
             │          │          │          │        (0b infra: docker/pgvector
          Track A    Track B    Track C    Track D       + skeletons, alongside 0a)
         Ingestion  Retrieval+ Frontend   Notes
          (Ph 1)    Chat (Ph2) (Ph 3)     (Ph 5)
             │        │ └─ publishes grounded-gen core ─┐
             └─▶ integrates ◀─┘                         ▼
                 (real chunks)                       Track E  Studio (Ph 4)
                                                         │
                                       Track F (stretch): Audio (Ph 6)
             └──────────────── all merge ─────────────▶ Phase 7 (eval/polish)
```

**Track assignments** (one agent per track; each owns its folders):

| Track | Phase | Owns (folders/files) | Depends on | Builds/tests against | Starts |
|---|---|---|---|---|---|
| **A** Ingestion | 1 | `services/ingestion/*`, `infrastructure/providers/bge_embeddings.py`, `api/routes/sources.py` | 0a (source/chunk schema, `EmbeddingProvider`) | real bge-m3 + sample files | after 0a |
| **B** Retrieval+Chat | 2 | `services/retrieval/*`, `services/chat/*`, `infrastructure/providers/anthropic_llm.py`, `infrastructure/persistence/pgvector_store.py`, `api/routes/chat.py` | 0a (`VectorStore`+`LLMProvider` ports, chunk schema) | seeded test chunks + **fake LLM**, then real | after 0a |
| **C** Frontend | 3 | `frontend/*` | 0a (API/OpenAPI contract) | **mock API server** | after 0a (parallel) |
| **D** Notes | 5 | `services/notes/*`, `api/routes/notes.py` | 0a (notebook/note schema) | DB; near-independent CRUD | after 0a (parallel) |
| **E** Studio | 4 | `services/studio/*`, `api/routes/studio.py` | **B's grounded-gen core** | B's core + fake LLM | after B publishes grounded-gen interface |
| **F** Audio (stretch) | 6 | `services/audio/*`, `infrastructure/providers/tts_*`, `api/routes/audio.py` | B core + `TTSProvider` port | fake TTS | deferred / parallel |

**Why this parallelizes cleanly:** the modular architecture means each track edits
its **own folder**. Chat and Studio share exactly one thing — the
grounded-generation core (retrieve → grounded prompt → citation map) — so **Track
B owns and publishes that as a reusable function early**, and Track E composes it.
The frontend never blocks: it builds against the OpenAPI contract with a mock
server and switches to the live backend at integration.

**Merge-safety rules (required for multi-agent work):**
- Each agent works in its **own git worktree / branch**; integrate via PRs.
- **Freeze the contracts during a sprint.** Edits to `domain/ports`, `config.py`,
  `api/deps.py`, and the initial migration are shared, high-contention — coordinate
  them, don't change them ad hoc per track.
- Put the **entire initial schema in the 0a migration** so feature tracks rarely
  add migrations early (avoids migration-ordering conflicts).
- `main.py` router registration and `api/deps.py` bindings are the only shared
  touch points: each feature module **exposes a `router`** and main aggregates
  them; keep these edits small and additive.
- Every track ships **fakes** for the ports it consumes so it never blocks on
  another track.

**Critical path:** `0a → (A ∥ B) → B core → E → 7`, with **C and D running in
parallel the whole time** and **F deferred**. Realistic concurrency after 0a:
**4–5 agents** (A, B, C, D; then E once B's core lands).

---

## Phase 0 — Scaffolding & infrastructure ☑

### Phase 0a — Contracts (GATE: do first, single agent) ☑
**Goal:** the shared foundation every track builds against. Nothing fans out until this lands.
- ☑ Repo layout: `backend/`, `frontend/`, `docker-compose.yml`, `.env.example`, README.
- ☑ DB schema + **single first migration** covering the full data model above (9 tables + pgvector + HNSW index).
- ☑ `domain/ports` interfaces: `EmbeddingProvider`, `LLMProvider`, `TTSProvider`, `VectorStore`, 8 repositories.
- ☑ Composition root (`config.py` + `api/deps.py`) binding ports → adapters from env (fakes when no key).
- ☑ API/OpenAPI contract: 13 endpoint paths (notebooks live; sources/chat/studio/notes/audio = contract stubs).
- ☑ FastAPI app factory + module-router registration pattern in `main.py`.

**Done when:** backend starts, OpenAPI schema is published, ports + migration exist; tracks can begin against the contract. ✓

### Phase 0b — Infra & skeletons (alongside 0a) ☑
- ☑ docker-compose: Postgres + pgvector; Alembic wired.
- ☑ React + Vite + TS skeleton; typed API client (mirrors contract); three-pane layout shell (German) + empty state.
- ☑ Health endpoint green; backend health indicator in the UI.

**Done when:** `docker-compose up` + backend + frontend run; health check green. ✓

**Phase 0 verification:** 9 backend pytest passing (contracts, health, notebook CRUD vs live Postgres); `ruff` clean; live uvicorn smoke (health/create/list/501-stub); frontend `npm run build` passes. Known gap: **`ANTHROPIC_API_KEY` not set** → real LLM deferred; fake LLM path active. Execution note: background sub-agents did not survive the host process this session (see review) — track-execution mechanics to be decided before fan-out.

## Phase 1 — Source ingestion ☑
**Track A** · after 0a · parallel with B/C/D.
**Goal:** add sources and turn them into searchable, embedded chunks.
- ☐ Endpoints: create notebook; add source via file upload (PDF, txt/md), pasted text, URL.
- ☐ Extraction: PDF text (pypdf/pdfplumber), HTML→text for URLs, plain text passthrough.
- ☐ Chunking: token-aware splitter with overlap; preserve char offsets for citations.
- ☐ Embedding: `BgeM3Local` adapter; batch embed; store vectors in pgvector.
- ☐ Source status lifecycle (processing → ready → error); surface in API.

**Done when:** uploading a PDF yields ready chunks with embeddings; counts visible via API.

## Phase 2 — Grounded chat with citations (CORE) ☑
**Track B** · after 0a · parallel with A/C/D · publishes the reusable grounded-generation core for Studio (E).
**Goal:** the heart of the product — faithful, cited Q&A.
- ☐ Retrieval: vector search scoped to notebook, top-k; (optional) lightweight rerank.
- ☐ Grounding prompt: numbered chunks, strict "only use sources / refuse if absent" instructions.
- ☐ `AnthropicProvider` (Haiku 4.5); structured output for answer + per-claim citation ids.
- ☐ Citation mapping: chunk id → source + char span; persist `citation` rows.
- ☐ Refusal behavior when retrieval is empty/weak.
- ☐ Stream answer to frontend (SSE).

**Done when:** asking an in-source question returns a cited answer; an out-of-source question is refused.

## Phase 3 — Frontend core UX ☑
**Track C** · after 0a · parallel from start against the OpenAPI mock; integrate when endpoints are live.
**Design source of truth:** [`design/CloneLM-frontend.excalidraw`](design/CloneLM-frontend.excalidraw) (main view) and [`design/CloneLM-empty.excalidraw`](design/CloneLM-empty.excalidraw) (empty state). **UI copy is German.** The design color-maps regions to backend tracks (Quellen→A, Chat→B, Studio→E, Notes→D).
**Goal:** reproduce the designed three-pane NotebookLM experience.

Layout (per the design):
- ☐ Top bar: `CloneLM` logo + notebook title · `+ Neues Notebook` · `Teilen` · `Einstellungen`.
- ☐ **Quellen** pane (left · Track A data): `+ Quellen hinzufügen`, `Web-Recherche`, source list with type badge (PDF…) + status (`bereit`), `Alle auswählen` + per-source checkbox.
- ☐ **Chat** pane (middle · Track B data): source/summary header (`N Quelle(n) · date`), suggested-question chips, streamed answers with inline citation chips `[1]`, `In Notiz speichern`, input `Text eingeben…`.
- ☐ **Studio** pane (right · Track E/D): tiles `Zusammenfassung` · `FAQ` · `Study Guide` · `Briefing` · `Timeline` · `Audio (Stretch)`; "Generierte Artefakte (als Notiz speicherbar)"; `+ Notiz hinzufügen`.
- ☐ **Modal — Quellen hinzufügen** (trigger `+ Quellen hinzufügen`): `Hochladen` · `Websites` · `Drive` · `Text einfügen`; supports PDF · Bilder · Dokumente · Audio · Text · URL.
- ☐ **Modal — Beleg-Ansicht** (trigger: click citation chip `[1]`): source · page · section + highlighted exact passage (Track B span mapping).
- ☐ **Empty state** (0 sources): chat input & Studio tiles **disabled** until ≥ 1 source is `bereit`; placeholder copy per `CloneLM-empty.excalidraw`.
- ☐ Loading / error states.

**Done when:** the UI matches the design and supports the full loop (create → add sources → chat → inspect citations → save note) against the live backend.

## Phase 4 — Studio outputs ☑
**Track E** · after Track B's grounded-gen core lands · parallel with C/D.
**Goal:** one-click grounded artifacts.
- ☐ Summary, FAQ, Study guide, Briefing doc, Timeline — each grounded + cited.
- ☐ Shared generation path (retrieve broadly → grounded synthesis → citations).
- ☐ Use Sonnet 4.6 via the same `LLMProvider` for heavier synthesis (config per task).
- ☐ UI: Studio panel to generate/view artifacts.

**Done when:** each artifact generates from real sources with citations.

## Phase 5 — Saved notes ☑
**Track D** · after 0a · near-independent CRUD, parallel from start.
**Goal:** capture answers/artifacts.
- ☐ Save a chat answer or Studio output as a note; manual notes too.
- ☐ List/edit/delete notes per notebook.
- ☐ UI: notes panel.

**Done when:** notes persist and are manageable per notebook.

## Phase 6 — Audio Overview (STRETCH) ☑
**Track F (stretch)** · after Track B core + `TTSProvider` port · deferrable, parallel-capable.
**Goal:** podcast-style two-host overview from sources.
- ☐ Grounded two-host dialogue script (Sonnet 4.6).
- ☐ TTS backend (pluggable) → audio file; store + serve.
- ☐ UI: generate + play.

**Done when:** a notebook produces a playable, source-grounded audio overview.

## Phase 7 — Faithfulness eval, polish, delivery ☑
**Convergence** · after tracks merge · not parallel.
**Goal:** prove the north star and ship the demo.
- ☐ Lightweight groundedness check (verify cited chunks support claims) — optional second pass (not implemented; refusal already covers the empty/uncited cases).
- ☑ Small eval set: in-source (must answer+cite) vs out-of-source (must refuse) — offline `tests/test_faithfulness_eval.py` (CI-safe) + live `scripts/faithfulness_demo.py` (real providers, 4/4).
- ☑ README: setup, architecture, design decisions (faithfulness + provider abstraction), run + eval steps.
- ☑ Demo prep: bundled sample sources + one-command live faithfulness demo. (Recording the Loom / submitting the agent session is the human delivery step.)

**Done when:** eval passes, docs complete, demo recorded. ✓ (eval + docs done; recording is the human step)

## Phase 8 — Frontend E2E test & post-launch fixes ☑
**Convergence** · browser-driven E2E test of the live app (browser-use) over the **real**
stack (Anthropic + bge-m3), then fixes for what it surfaced.
**Test artifacts:** [`design/frontend-test-plan.md`](design/frontend-test-plan.md) ·
[`design/frontend-test-report.md`](design/frontend-test-report.md). Scenarios S0–S7:
empty-state gating, paste ingestion → `bereit`, grounded cited chat, Beleg-Ansicht
click-through, refusal, Studio artifact + save-as-note, note CRUD. North star (cited answer
+ traceable evidence + refusal) verified end-to-end.

**Findings & fixes (each committed atomically on `fix/sse-rendering-and-studio-citations`):**
- **F3 — chat stuck on "…" (critical).** The frontend SSE parser split events on `"\n\n"`,
  but sse-starlette delimits events with CRLF (`"\r\n\r\n"`), which contains no `"\n\n"` → no
  event was ever dispatched. Fix: normalize CRLF/CR→LF before splitting
  ([`frontend/src/api/client.ts`](frontend/src/api/client.ts)). Live-verified.
- **F1 — Study Guide rendered as raw JSON.** Long artifacts exhausted `max_tokens` (1024)
  mid-JSON; `json.loads` failed and the raw `{"answer":…}` wrapper (literal `\n`, 0 citations)
  was stored. Fix: tolerant salvage parser
  ([`services/chat/grounding.py`](backend/app/services/chat/grounding.py)) **+** a
  Studio-specific budget `studio_max_tokens=4096`
  ([`config.py`](backend/app/config.py) + [`api/routes/studio.py`](backend/app/api/routes/studio.py)).
  Live-verified: clean markdown with a citation.
- **F2 — summary/briefing citations unreachable.** The shared prompt asked for citations in
  the structured array but never inline, so prose kinds omitted `[n]` and no chip rendered.
  Fix: prompt now requires inline markers + bidirectional consistency
  ([`services/chat/prompts.py`](backend/app/services/chat/prompts.py)); **+** a deterministic
  "Belege:" footer for any citation lacking an inline marker
  ([`ChatPane.tsx`](frontend/src/components/ChatPane.tsx) + [`StudioPane.tsx`](frontend/src/components/StudioPane.tsx)).

**Verification:** `ruff` clean · **73 backend pytest passing** · frontend `tsc` clean · live
in-browser: S3 (cited answer) · chat citation → Beleg-Ansicht · S5 (refusal) · study-guide
clean render.
**Observation (out of scope, not fixed):** a backend reload re-seeds demo `Studio-*`
notebooks (notebook-list clutter) — flagged for separate triage.

**Done when:** the E2E loop renders correctly in a real browser and the three findings are
fixed + verified. ✓

---

## Decisions log
- **2026-06-19** — Stack: FastAPI + React(TS) + Postgres/pgvector.
- **2026-06-19** — Scope: core grounded chat + Studio outputs + Notes + URL ingestion + Audio Overview (stretch).
- **2026-06-19** — LLM: Claude Haiku 4.5, behind pluggable `LLMProvider` (single publisher; Sonnet 4.6 for heavy synthesis; Qwen3/Cohere documented alternatives).
- **2026-06-19** — Embeddings: local **bge-m3** behind pluggable `EmbeddingProvider` (no second SaaS vendor; strong multilingual incl. German; Voyage as fallback).
- **2026-06-19** — Faithfulness is architectural (RAG + mandatory citations + refusal), not model-size driven.
- **2026-06-19** — Execution: contracts-first (Phase 0a gate, single agent) then parallel tracks A–F; agents work in separate git worktrees, one folder per track, contracts frozen during a sprint.
- **2026-06-19** — Frontend design is fixed by `design/CloneLM-*.excalidraw` (German UI, three-pane layout + two modals + empty state); it is the source of truth for Track C.
- **2026-06-21** — Execution mechanics: background sub-agents/worktrees were unavailable in the session, so Tracks A–D ran as **parallel foreground sub-agents** against the frozen Phase-0 contracts (user decision). Cross-track contracts fixed at fan-out: source add = multipart form; chat = SSE (meta/token/citation/done/error).
- **2026-06-21** — AI realism: real **bge-m3** (local) + real **Claude Haiku 4.5** enabled. Live faithfulness verified end-to-end: in-source question → grounded, cited German answer; out-of-source question → explicit refusal, zero citations. 51 backend tests green; frontend build green.
- **2026-06-21** — Frontend E2E test (browser-use) over the real stack surfaced 3 bugs, all fixed on `fix/sse-rendering-and-studio-citations` (atomic commits): chat SSE not rendering (CRLF vs `\n\n` parser), Studio study-guide stored as raw truncated JSON (tolerant parser + larger Studio token budget), and citations without inline markers being unreachable (prompt requires inline markers + UI "Belege:" fallback). Diagnosed by 3 parallel agents in isolated worktrees. See **Phase 8**.

---

## Status snapshot (2026-06-21) — ALL PHASES COMPLETE
- ☑ Phase 0 · ☑ Phase 1 Ingestion (A) · ☑ Phase 2 Grounded chat CORE (B) · ☑ Phase 3 Frontend UX (C) · ☑ Phase 4 Studio (E) · ☑ Phase 5 Notes (D) · ☑ Phase 6 Audio stretch (F) · ☑ Phase 7 eval/docs/polish · ☑ Phase 8 E2E test & fixes
- Verification: **73 backend pytest passing**, `ruff` clean (app/tests/scripts), frontend `tsc` + `npm run build` green. Live real-provider results: grounded cited chat + refusal; Studio summary/FAQ cited; playable WAV audio overview; **faithfulness eval 4/4** (`scripts/faithfulness_demo.py`). Browser-use E2E (S0–S7) passing after the Phase 8 fixes (chat SSE render · study-guide clean render · citation reachability).
- Remaining human step: record the Loom / submit the agent session for delivery.
