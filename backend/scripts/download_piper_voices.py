"""Pre-download the Piper voice models used by the Audio Overview.

Running this up front means the first ``POST /api/notebooks/{id}/audio`` request
doesn't pay the (one-time) model download. The voices and target directory are
read from the app Settings so this stays in sync with config/env.

Usage:
    uv run --extra audio python scripts/download_piper_voices.py
"""
from __future__ import annotations

from pathlib import Path

from app.config import get_settings

_BACKEND_ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    from piper.download_voices import download_voice

    s = get_settings()
    voice_dir = Path(s.piper_voice_dir)
    if not voice_dir.is_absolute():
        voice_dir = _BACKEND_ROOT / s.piper_voice_dir
    voice_dir.mkdir(parents=True, exist_ok=True)

    for name in {s.piper_voice_host_a, s.piper_voice_host_b}:
        if (voice_dir / f"{name}.onnx").is_file():
            print(f"✓ {name} already present")
            continue
        print(f"↓ downloading {name} …")
        download_voice(name, voice_dir)
        print(f"✓ {name}")

    print(f"Piper voices ready in {voice_dir}")


if __name__ == "__main__":
    main()
