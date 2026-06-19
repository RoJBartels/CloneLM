"""Fake TTSProvider — emits a tiny silent WAV so the Audio Overview loop is
exercisable without a real TTS backend (stretch track)."""
from __future__ import annotations

import struct

from app.domain.ports.tts import TTSProvider, TTSSegment


def _silent_wav(seconds: float = 1.0, sample_rate: int = 8000) -> bytes:
    n = int(seconds * sample_rate)
    data = b"\x00\x00" * n
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    return header + data


class FakeTTSProvider(TTSProvider):
    @property
    def model_id(self) -> str:
        return "fake-tts-v1"

    @property
    def audio_format(self) -> str:
        return "wav"

    def synthesize(self, segments: list[TTSSegment]) -> bytes:
        # Length roughly proportional to the script so output isn't trivially empty.
        total_chars = sum(len(s.text) for s in segments) or 1
        seconds = min(30.0, max(1.0, total_chars / 200.0))
        return _silent_wav(seconds=seconds)
