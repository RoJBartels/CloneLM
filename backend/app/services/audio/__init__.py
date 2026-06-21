"""Audio Overview service (Track F, Phase 6 — STRETCH).

Produces a grounded, two-host podcast-style dialogue from a notebook's sources
and renders it through the pluggable ``TTSProvider`` port.

    from app.services.audio import AudioService

Depends only on ``domain/ports``, ``services/chat`` (the published
``GroundedGenerator``), and the injected repository/provider instances — never
on a vendor SDK directly.
"""
from __future__ import annotations

from .script import build_script
from .service import AudioService

__all__ = ["AudioService", "build_script"]
