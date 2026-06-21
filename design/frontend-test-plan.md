# CloneLM — Frontend E2E Test Plan (browser-use)

Derived from the design source of truth (`design/CloneLM-empty.excalidraw`,
`design/CloneLM-frontend.excalidraw`) and the real implemented UI in
`frontend/src`. To be executed with the `browser-use` MCP tools.

## Objective

Prove the product's **north star — faithfulness** — through the UI, plus the full
happy path the design annotates as Tracks A/B/D/E:

1. **Empty state** gating (0 sources ⇒ chat + Studio disabled). *(empty.excalidraw)*
2. **Track A** — add a source; status `verarbeitet…` → `bereit`.
3. **Track B** — grounded chat with inline `[n]` citation chips.
4. **Beleg-Ansicht** — click `[n]` ⇒ the exact supporting passage (the faithfulness payoff).
5. **Refusal** — an out-of-scope question is refused, not answered from world knowledge.
6. **Track E** — a Studio artifact is generated, grounded + cited.
7. **Track D** — save an artifact as a note; create/edit/delete a manual note.

The single most important assertions are **#3+#4 (grounded + traceable)** and
**#5 (refusal)** — these are the hiring task's whole point.

## Environment / preconditions (verified live)

| Thing | State |
|---|---|
| Frontend | Vite dev server at **http://localhost:5173** (proxies `/api`, `/health`) |
| Backend | uvicorn at :8000, `/health` = `ok` |
| Providers | **REAL**: `LLM_PROVIDER=anthropic` (Haiku 4.5 chat / Sonnet 4.6 Studio), `EMBEDDING_PROVIDER=bge_m3_local` |
| DB | Postgres+pgvector healthy on :5432 |

Because providers are real, chat/Studio output is **non-deterministic in wording**.
Assertions therefore check *structure/behavior* (a citation chip exists, a turn is
flagged refused, a badge flips to `bereit`) — **never exact answer text**.

## Test data (self-contained, German — typed via the "Text einfügen" tab)

Using paste (not file-upload/URL) keeps the test deterministic: no hidden-input
file picker, no network fetch.

- **Title:** `Photosynthese — Kurzüberblick`
- **Content:**
  > Die Photosynthese ist der Prozess, mit dem Pflanzen Lichtenergie in chemische
  > Energie umwandeln. Sie findet in den Chloroplasten statt, genauer in den
  > Thylakoidmembranen. Das grüne Pigment Chlorophyll absorbiert vor allem rotes
  > und blaues Licht. In der Lichtreaktion wird Wasser gespalten und Sauerstoff
  > freigesetzt. In der Dunkelreaktion (Calvin-Zyklus) wird Kohlenstoffdioxid zu
  > Glucose fixiert. Die Nettogleichung lautet: 6 CO2 + 6 H2O → C6H12O6 + 6 O2.

- **Supported question (expect answer + ≥1 `[n]` chip):**
  `Wo findet die Photosynthese statt und welches Pigment absorbiert das Licht?`
- **Unsupported question (expect refusal, 0 chips):**
  `Wie hoch ist der Mount Everest?`

## Tooling approach

Deterministic, step-by-step with the granular browser-use MCP tools
(`browser_navigate`, `browser_get_state`, `browser_click`, `browser_type`,
`browser_scroll`, `browser_screenshot`) — **not** the autonomous agent — so each
step has an explicit assertion. Use `browser_get_state` before each interaction to
resolve the current element indices; screenshot at every milestone (✦).

**Waiting strategy** (no `sleep`): re-poll `browser_get_state` until the expected
text/element appears, then proceed.
- Source ready: poll until the source row shows **`bereit`** (frontend polls every 2 s; allow ~30 s).
- Chat done: poll until the assistant bubble shows the **`In Notiz speichern`** button (only rendered when streaming finished with content) *or* the **`Keine Antwort aus den Quellen ableitbar`** refusal banner.
- Studio done: poll until a new artifact card appears in the Studio list (Sonnet — allow ~45 s).

---

## Steps

### S0 — Load app on a fresh notebook
1. `browser_navigate` → `http://localhost:5173`.
2. `browser_get_state`; ✦ screenshot.
3. Click **`+ Neues Notebook`** (TopBar) to guarantee a clean 0-source notebook
   (bootstrap otherwise loads an arbitrary existing notebook).

**Expect:** TopBar shows `CloneLM`, a `· Unbenanntes Notebook` title, and a green
status dot with **`Verbunden`**. Three panes visible: **Quellen / Chat / Studio**.

### S1 — Empty-state gating *(empty.excalidraw invariant)*
4. Inspect state (no clicks).

**Expect:**
- Chat center shows the notebook title, `0 Quellen · <date>`, and the dashed banner
  **`Fügen Sie eine Quelle hinzu, um Fragen zu stellen.`**
- Chat input (`Text eingeben…`) is **disabled**; round **`Senden`** (`↑`) button disabled.
- Studio tiles (`Zusammenfassung`, `FAQ`, `Study Guide`, `Briefing`, `Timeline`) and
  `Audio (Stretch)` are **disabled** (dimmed); Studio body shows the
  `Hier wird die Ausgabe von Studio gespeichert…` placeholder.
- Quellen pane shows the empty hint `Gespeicherte Quellen werden hier angezeigt`.
- ✦ screenshot.

### S2 — Add a source via paste *(Track A)*
5. Click **`+ Quellen hinzufügen`** → modal **`Quellen hinzufügen`** opens.
6. Click the **`Text einfügen`** tab.
7. `browser_type` the **Title** into the `Titel (optional)` field.
8. `browser_type` the **Content** into the `Text einfügen…` textarea.
9. Click **`Hinzufügen`**. ✦ screenshot (modal mid-submit optional).

**Expect:** modal closes; a source row appears in Quellen with a **`TXT`** badge and
the title `Photosynthese — Kurzüberblick`, initially **`verarbeitet…`**.
10. Poll `browser_get_state` until the row shows **`bereit`**. ✦ screenshot.

**Expect after ready:** chat input becomes **enabled**; Studio tiles become enabled;
the empty banner is replaced by the two suggested-question buttons; chat footer shows
`1 Quellen`.

### S3 — Grounded, cited answer *(Track B — core)*
11. `browser_type` the **supported question** into the chat input; press Enter (or click `↑`).
12. Poll until the assistant bubble finishes (the `In Notiz speichern` button appears).
13. ✦ screenshot.

**Assert (must all hold):**
- An assistant bubble is present with non-empty text.
- It contains **≥ 1 citation chip** rendered as `[1]` (amber, clickable button).
- It is **NOT** marked refused (no `Keine Antwort aus den Quellen ableitbar` banner).

### S4 — Beleg-Ansicht (traceability payoff) *(faithfulness)*
14. Click the **`[1]`** chip in the assistant answer.
15. `browser_get_state`; ✦ screenshot.

**Assert:** a modal **`Beleg-Ansicht`** opens showing:
- the **source title** `Photosynthese — Kurzüberblick`,
- a `Zeichen <start>–<end>` line,
- a **non-empty quoted snippet** (`„…“ [1]`) — the literal supporting passage,
- the footer `Diese Passage stammt direkt aus der Quelle…`.
16. Close the modal (✕ / `browser_get_state` to find close control).

### S5 — Refusal on an unsupported question *(north star)*
17. `browser_type` the **unsupported question** (`Wie hoch ist der Mount Everest?`); send.
18. Poll until the assistant bubble finishes.
19. ✦ screenshot.

**Assert:**
- The assistant bubble shows the refusal banner **`Keine Antwort aus den Quellen ableitbar`**.
- It contains **0 citation chips**.
- No fabricated altitude/world-knowledge answer is presented as grounded.

### S6 — Studio artifact, grounded + cited *(Track E)* → save as note *(Track D)*
20. Click the **`Zusammenfassung`** Studio tile.
21. Poll until a new artifact card appears in the Studio body (allow ~45 s, Sonnet). ✦ screenshot.

**Assert:** an artifact card titled like `Zusammenfassung` appears with body text and
**≥ 1 `[n]` citation chip**. (Optional: click its chip → Beleg-Ansicht opens, same as S4.)

22. Click **`In Notiz speichern`** on that artifact card.

**Assert:** a note entry appears in the Studio list (under `Generierte Artefakte`) with
edit `✎` / delete `✕` controls. ✦ screenshot.

### S7 — Manual note CRUD *(Track D)*
23. Click **`+ Notiz hinzufügen`** → modal **`Notiz hinzufügen`**.
24. Type `Titel` = `Testnotiz`, `Inhalt…` = `Von browser-use erstellt.`; click **`Speichern`**.

**Assert:** the new note `Testnotiz` appears in the Studio list.
25. Click its **`✎`** → modal **`Notiz bearbeiten`**; append ` (bearbeitet)` to title; **`Speichern`**.

**Assert:** title updates to `Testnotiz (bearbeitet)`.
26. Click its **`✕`**.

**Assert:** the note is removed from the list. ✦ final screenshot.

### S8 — (Optional) source-scoping sanity
27. With a second source added later this could verify isolation; with one source,
    just confirm the `Alle auswählen` checkbox toggles and the chat footer source
    count reflects selection. *(Low priority; skip if time-boxed.)*

---

## Pass / Fail criteria

**PASS** requires all of:
- S1 gating holds (chat + Studio disabled at 0 sources).
- S2 source reaches `bereit`.
- **S3 answer carries ≥1 clickable `[n]` chip and is not refused.**
- **S4 Beleg-Ansicht shows a non-empty literal snippet from the named source.**
- **S5 unsupported question is refused with 0 citations.**
- S6 Studio artifact is generated with ≥1 citation and is saveable as a note.
- S7 manual note create/edit/delete all reflect in the UI.

Any failure in **S3/S4/S5** is a north-star failure and fails the suite regardless of
the rest.

## Risks / notes

- **Real-LLM nondeterminism:** assert structure (chip present, refused flag), never
  exact wording. If a supported question ever returns 0 chips, retry once with the
  second phrasing before failing.
- **Timing:** Studio uses Sonnet and can take tens of seconds; poll, don't assume.
- **State pollution:** the test creates one notebook + sources/notes. This is additive
  and harmless; no cleanup required (a `+ Neues Notebook` per run isolates it).
- **Element indices** from `browser_get_state` shift between renders — always re-fetch
  state immediately before each click; match by visible German label, not a cached index.
