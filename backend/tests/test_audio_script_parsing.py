"""Unit tests for the Host A / Host B script parser (no DB, no network).

``build_script`` composes ``GroundedGenerator`` (Track B core, already tested
in ``test_chat_grounding.py``) with the line parser in
``app.services.audio.script``. These tests isolate just the parser so the
segment-splitting logic has direct coverage independent of the full pipeline.
"""
from __future__ import annotations

from app.services.audio.script import parse_segments


def test_parses_alternating_host_lines():
    text = (
        "Host A: Willkommen zur Übersicht!\n"
        "Host B: Schön, hier zu sein.\n"
        "Host A: Lass uns einsteigen."
    )
    segments = parse_segments(text)
    assert [s.speaker for s in segments] == ["host_a", "host_b", "host_a"]
    assert segments[0].text == "Willkommen zur Übersicht!"
    assert segments[1].text == "Schön, hier zu sein."


def test_parses_case_insensitive_and_spaced_labels():
    text = "host a: Hallo.\nHOST B : Hi zurück."
    segments = parse_segments(text)
    assert [s.speaker for s in segments] == ["host_a", "host_b"]


def test_ignores_blank_lines():
    text = "Host A: Erste Zeile.\n\n\nHost B: Zweite Zeile."
    segments = parse_segments(text)
    assert len(segments) == 2


def test_falls_back_to_single_segment_when_unparseable():
    text = "Dies ist einfach ein Fließtext ohne Sprecher-Präfixe."
    segments = parse_segments(text)
    assert len(segments) == 1
    assert segments[0].speaker == "host_a"
    assert segments[0].text == text


def test_empty_text_yields_no_segments():
    assert parse_segments("") == []
    assert parse_segments("   \n  \n") == []
