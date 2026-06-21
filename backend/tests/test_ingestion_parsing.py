"""Unit tests for source text extraction (txt/md passthrough, HTML->text)."""
from __future__ import annotations

from app.services.ingestion.parsing import extract_html, extract_plain_text


def test_plain_text_passthrough_str():
    extracted = extract_plain_text("Hallo Welt\nZweite Zeile")
    assert extracted.text == "Hallo Welt\nZweite Zeile"


def test_plain_text_passthrough_bytes_utf8():
    extracted = extract_plain_text("Grüße ü ö ä".encode("utf-8"))
    assert extracted.text == "Grüße ü ö ä"


def test_html_strips_tags_and_scripts():
    html = """
    <html><head><style>.x{color:red}</style></head>
    <body>
      <script>alert('x')</script>
      <h1>Titel</h1>
      <p>Erster Absatz.</p>
      <p>Zweiter   Absatz   mit   Leerzeichen.</p>
    </body></html>
    """
    extracted = extract_html(html)
    assert "<" not in extracted.text
    assert "alert" not in extracted.text
    assert "color:red" not in extracted.text
    assert "Titel" in extracted.text
    assert "Erster Absatz." in extracted.text
    # whitespace collapsed
    assert "Zweiter Absatz mit Leerzeichen." in extracted.text


def test_html_collapses_whitespace():
    html = "<p>a</p>\n\n\n<p>   b   </p>"
    extracted = extract_html(html)
    assert "  " not in extracted.text
