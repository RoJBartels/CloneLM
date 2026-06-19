"""TTSProvider port (stretch — Audio Overview). Implemented by infrastructure
adapters; vendor TTS SDKs live only in those adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TTSSegment:
    """One line of the two-host dialogue."""

    speaker: str  # e.g. "host_a" | "host_b"
    text: str


class TTSProvider(ABC):
    @property
    @abstractmethod
    def model_id(self) -> str: ...

    @property
    @abstractmethod
    def audio_format(self) -> str:
        """File extension / container, e.g. ``mp3`` or ``wav``."""

    @abstractmethod
    def synthesize(self, segments: list[TTSSegment]) -> bytes:
        """Render the dialogue to a single audio blob."""
