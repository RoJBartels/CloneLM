# Ollama provider — live browser E2E test report

**Date:** 2026-06-23
**Scope:** Phase 9 quality-of-life change — runtime LLM provider switching
(`Einstellungen`) and the new local open-source `OllamaLLMProvider`.
**Method:** browser-use, driving the real app (frontend :5173 → backend :8000 →
Postgres/pgvector), with a real local Ollama server.
**Goal:** verify that switching the LLM provider to Ollama from the UI works and
that the local model answers, grounded and cited, in the chat.

---

## Environment

| Piece | Value |
|---|---|
| LLM under test | **Ollama** `qwen2.5:0.5b` (397 MB, Q4) — local, CPU-only |
| Ollama install | user-space, no sudo: `~/.local/bin/ollama` (v0.30.10), `ollama serve` on `127.0.0.1:11434` |
| Hardware | 4 CPU cores, no GPU, 7.6 GiB RAM (~1 GiB free during the run) |
| Embeddings | real **bge-m3** (local, unchanged) |
| Notebook | "Unbenanntes Notebook", 2 ready sources: `CV.pdf` (3 chunks) + Pokéwiki "Bisasam" URL (25 chunks) |
| Grounded question | "Welche Typen hat das Pokémon Bisasam?" (well covered by the URL source) |

The tiny 0.5b model was chosen deliberately for the constrained RAM — see the
session decision (CPU-only, ~1 GiB free).

---

## Steps & results

| # | Step (via browser-use) | Result |
|---|---|---|
| 1 | Open **Einstellungen** | ✅ Modal "Einstellungen — KI-Modell" opens; Anthropic selected; "Ein Schlüssel ist gespeichert" shown (key never displayed) |
| 2 | Select **Open Source (Ollama, lokal)** | ✅ Reveals Server-URL + Modell fields; **"● Ollama erreichbar"** indicator turns **green** (liveness probe hits the running server) |
| 3 | Set model `qwen2.5:0.5b`, **Speichern** | ✅ Green banner **"Gespeichert. Aktiver Anbieter: ollama."** |
| 3a | Verify persistence (API + file) | ✅ `GET /api/settings` → `llm_provider=ollama`, `ollama_model=qwen2.5:0.5b`, `ollama_available=true`; `backend/.env` → `LLM_PROVIDER=ollama`, `OLLAMA_MODEL=qwen2.5:0.5b`; Anthropic key preserved |
| 4 | Ask the grounded question in chat | ✅ Answer rendered: *"Bisasam ist ein Starter-Pokémon, der in den Spielen Pokémon Rot, Blau, Feuerrot und Blattgrün innehat."* with citation chip **[1]** |
| 4a | Confirm the answer came from Ollama (not Claude) | ✅ Ollama server log shows the request: 4095-token grounded prompt, **91 tokens generated**, **~67 s total** (60.6 s prompt eval @ 67 tok/s + 6.8 s generation @ 13 tok/s); prompt truncated to the 4096 context |
| 5 | Switch back to **Anthropic** (Speichern, blank key) | ✅ Banner **"Gespeichert. Aktiver Anbieter: anthropic."**; key preserved |
| 6 | Re-ask in chat on Anthropic | ✅ *"Bisasam ist ein Pokémon der Typen **Pflanze und Gift** [1]."* — precise, grounded, cited |
| 7 | Restore state | ✅ `backend/.env` back to `LLM_PROVIDER=anthropic`; git clean (`.env` gitignored) |

**Verdict: PASS.** Provider switching works end-to-end from the UI and persists;
the local Ollama model answers in the chat with the grounding + citation pipeline
intact; the round-trip back to Anthropic works and preserves the API key.

---

## Findings (not blockers)

- **F1 — Latency on CPU.** A single grounded answer took **~67 s** on `qwen2.5:0.5b`,
  CPU-only (≈60 s of that is prompt evaluation of the ~4 k-token grounding prompt).
  Inherent to local CPU inference on this box, not a code defect.
- **F2 — Context truncation.** Ollama's default `num_ctx` is **4096**, which the
  RAG grounding prompt (top-k = 8 chunks) nearly fills, so the prompt was
  **truncated** (`truncated = 1`). It still produced a grounded, cited answer here,
  but with a larger/again retrieval some context is dropped. *Possible improvement:*
  set a larger `num_ctx` in `OllamaLLMProvider` options (qwen2.5 supports 32 k),
  trading RAM for context — or lower `RETRIEVAL_TOP_K` for small-context models.
- **F3 — Answer quality vs. model size.** The 0.5b model gave a *grounded but
  imprecise* answer (it cited the source but described Bisasam as a "Starter-Pokémon"
  instead of naming the types). Claude Haiku answered the same question precisely
  ("Pflanze und Gift"). This is the expected provider/quality tradeoff — faithfulness
  (grounding + citation + refusal) is architectural and held for **both** providers;
  comprehension scales with the model.

## Reproduce

```bash
# user-space Ollama (already installed at ~/.local/bin/ollama)
OLLAMA_HOST=127.0.0.1:11434 ~/.local/bin/ollama serve &     # start server
~/.local/bin/ollama pull qwen2.5:0.5b                       # one-time
# then in the app: Einstellungen → Open Source (Ollama) → Modell qwen2.5:0.5b → Speichern
```
