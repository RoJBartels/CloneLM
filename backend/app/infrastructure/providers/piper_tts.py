"""Local Piper TTSProvider — real neural speech for the Audio Overview.

Renders the grounded two-host German dialogue with two distinct Piper voices
(``host_a`` / ``host_b``), fully offline after a one-time voice-model download.
The heavy ``piper-tts`` dependency is imported LAZILY and lives in the ``audio``
optional extra (``uv sync --extra audio``), mirroring the bge-m3 embeddings
adapter — so the app and the fake-provider path stay free of onnxruntime.

Voice models (``<voice>.onnx`` + ``.onnx.json``) are auto-downloaded into
``voice_dir`` on first use if missing; pre-fetch them with
``scripts/download_piper_voices.py`` to keep the first request fast.

The two default voices have different native sample rates (thorsten-medium is
22.05 kHz, kerstin-low is 16 kHz), so each turn is resampled to a single output
rate before concatenation. That uses the stdlib ``audioop`` module (present
through Python 3.12; on 3.13+ install the ``audioop-lts`` backport).
"""
from __future__ import annotations

import io
import os
import re
import wave
from pathlib import Path

from app.domain.ports.tts import TTSProvider, TTSSegment
from app.shared.logging import get_logger

log = get_logger(__name__)

# Inline citation markers like "[1]" are meaningful in the UI but must not be
# read aloud; strip them (and collapse the resulting whitespace) before TTS.
_CITATION_RE = re.compile(r"\[\d+\]")
_WS_RE = re.compile(r"\s+")

# Anchor relative voice dirs to the backend/ package root (not the process CWD),
# matching AudioService.STORAGE_DIR, so model lookup is stable regardless of
# where uvicorn/pytest is invoked from.
_BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _clean_for_speech(text: str) -> str:
    return _WS_RE.sub(" ", _CITATION_RE.sub("", text)).strip()


class PiperTTSProvider(TTSProvider):
    def __init__(
        self,
        *,
        voice_dir: str,
        voice_host_a: str,
        voice_host_b: str,
        output_sample_rate: int = 22050,
        gap_ms: int = 350,
    ) -> None:
        self._voice_dir = (
            voice_dir if os.path.isabs(voice_dir) else os.path.join(_BACKEND_ROOT, voice_dir)
        )
        self._voice_names: dict[str, str] = {"host_a": voice_host_a, "host_b": voice_host_b}
        self._default_voice = voice_host_a
        self._rate = output_sample_rate
        self._gap_ms = gap_ms
        self._loaded: dict[str, object] = {}  # voice_name -> PiperVoice (lazy)

    @property
    def model_id(self) -> str:
        return f"piper:{self._voice_names['host_a']}+{self._voice_names['host_b']}"

    @property
    def audio_format(self) -> str:
        return "wav"

    def is_available(self) -> bool:
        """Cheap check (no heavy import) used by the composition root to decide
        whether to bind this adapter or fall back to the fake one."""
        import importlib.util

        return importlib.util.find_spec("piper") is not None

    # -- internals --------------------------------------------------------- #
    def _voice(self, voice_name: str):
        if voice_name not in self._loaded:
            from piper import PiperVoice
            from piper.download_voices import download_voice

            model_path = os.path.join(self._voice_dir, f"{voice_name}.onnx")
            if not os.path.isfile(model_path):
                os.makedirs(self._voice_dir, exist_ok=True)
                log.info("Downloading Piper voice %s -> %s (first use)…", voice_name, self._voice_dir)
                download_voice(voice_name, Path(self._voice_dir))
            log.info("Loading Piper voice %s…", voice_name)
            self._loaded[voice_name] = PiperVoice.load(model_path)
        return self._loaded[voice_name]

    def _synth_turn(self, voice_name: str, text: str) -> bytes:
        """Render one turn to int16 PCM resampled to the output rate."""
        voice = self._voice(voice_name)
        raw = bytearray()
        native_rate = self._rate
        for chunk in voice.synthesize(text):
            raw += chunk.audio_int16_bytes
            native_rate = chunk.sample_rate
        if native_rate == self._rate:
            return bytes(raw)
        import audioop  # stdlib ≤3.12; on 3.13+ `pip install audioop-lts`

        converted, _ = audioop.ratecv(bytes(raw), 2, 1, native_rate, self._rate, None)
        return converted

    # -- port -------------------------------------------------------------- #
    def synthesize(self, segments: list[TTSSegment]) -> bytes:
        try:
            import piper  # noqa: F401  (fail fast with a clear, actionable message)
        except ImportError as exc:  # pragma: no cover - depends on the extra
            raise RuntimeError(
                "Piper TTS requires the 'audio' extra. Install it with "
                "`uv sync --extra audio` or set TTS_PROVIDER=fake."
            ) from exc

        gap = b"\x00\x00" * int(self._rate * self._gap_ms / 1000)
        pcm = bytearray()
        for seg in segments:
            text = _clean_for_speech(seg.text)
            if not text:
                continue
            voice_name = self._voice_names.get(seg.speaker, self._default_voice)
            if pcm:
                pcm += gap
            pcm += self._synth_turn(voice_name, text)

        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self._rate)
            wav.writeframes(bytes(pcm))
        return buf.getvalue()
