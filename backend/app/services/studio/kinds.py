"""Per-kind Studio task definitions (Track E, Phase 4).

For each ``StudioKind`` we define:
  - ``title``: the German display title persisted on the ``StudioOutput``.
  - ``query``: the retrieval driver passed to ``GroundedGenerator`` — written to
    pull broadly across the notebook's sources (Studio artifacts summarize the
    *whole* notebook, not a single question).
  - ``system_instructions``: the task-specific instruction inserted into the
    shared grounding prompt. The base prompt (``app.services.chat.prompts``)
    already enforces "answer ONLY from sources" + "cite every claim" + the
    refusal rule — these instructions only add the per-kind task framing.

No retrieval/citation logic lives here; this module is pure per-kind config.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.models import StudioKind


@dataclass(frozen=True)
class StudioKindSpec:
    title: str
    query: str
    system_instructions: str
    refusal_text: str


_SPECS: dict[StudioKind, StudioKindSpec] = {
    StudioKind.summary: StudioKindSpec(
        title="Zusammenfassung",
        query=(
            "Fasse die wichtigsten Themen, Aussagen und Erkenntnisse aller "
            "bereitgestellten Quellen zusammen."
        ),
        system_instructions=(
            "Write a concise summary (in German) of the core statements and "
            "key takeaways across ALL the provided sources. Cover the main "
            "topics broadly rather than going deep on a single detail. "
            "Structure the summary as short paragraphs or bullet points."
        ),
        refusal_text=(
            "Die bereitgestellten Quellen enthalten nicht genug Inhalt, um "
            "eine Zusammenfassung zu erstellen."
        ),
    ),
    StudioKind.faq: StudioKindSpec(
        title="FAQ",
        query=(
            "Welche wichtigen Fragen lassen sich aus den Quellen beantworten? "
            "Erstelle Fragen und Antworten zu den zentralen Themen."
        ),
        system_instructions=(
            "Derive a list of the most important Frequently Asked Questions "
            "(in German) that the provided sources can answer, together with "
            "their answers. Format as a sequence of 'Frage: ...' / 'Antwort: "
            "...' pairs. Only ask questions the sources actually answer."
        ),
        refusal_text=(
            "Die bereitgestellten Quellen enthalten nicht genug Inhalt, um "
            "eine FAQ zu erstellen."
        ),
    ),
    StudioKind.study_guide: StudioKindSpec(
        title="Study Guide",
        query=(
            "Was sind die Schlüsselkonzepte, Definitionen und wichtigsten "
            "Begriffe in den Quellen? Erstelle Wiederholungsfragen."
        ),
        system_instructions=(
            "Write a study guide (in German) covering: (1) key concepts and "
            "definitions found in the sources, (2) important terms explained "
            "in the sources' own words, and (3) a short list of review "
            "questions a student could use to test their understanding. "
            "Use clear section headings."
        ),
        refusal_text=(
            "Die bereitgestellten Quellen enthalten nicht genug Inhalt, um "
            "einen Study Guide zu erstellen."
        ),
    ),
    StudioKind.briefing: StudioKindSpec(
        title="Briefing",
        query=(
            "Erstelle ein kompaktes Executive-Briefing der wichtigsten "
            "Informationen, Implikationen und Schlussfolgerungen der Quellen."
        ),
        system_instructions=(
            "Write a compact executive briefing (in German) of the provided "
            "sources for someone who has no time to read them: the most "
            "important facts, implications, and conclusions, prioritized by "
            "importance. Keep it tight and decision-oriented."
        ),
        refusal_text=(
            "Die bereitgestellten Quellen enthalten nicht genug Inhalt, um "
            "ein Briefing zu erstellen."
        ),
    ),
    StudioKind.timeline: StudioKindSpec(
        title="Timeline",
        query=(
            "Welche Ereignisse, Daten und Zeitangaben werden in den Quellen "
            "genannt? Liste sie in chronologischer Reihenfolge auf."
        ),
        system_instructions=(
            "Extract all events, dates, and time references mentioned in the "
            "provided sources and present them (in German) as a chronological "
            "timeline, earliest first. Each entry should name the date/period "
            "and the associated event, grounded in a cited source. If the "
            "sources contain no temporal/chronological content at all, do NOT "
            "invent a timeline — follow the refusal rule instead."
        ),
        refusal_text=(
            "Die bereitgestellten Quellen enthalten keine erkennbare "
            "Chronologie oder Zeitangaben, um eine Timeline zu erstellen."
        ),
    ),
}


def get_spec(kind: StudioKind) -> StudioKindSpec:
    return _SPECS[kind]
