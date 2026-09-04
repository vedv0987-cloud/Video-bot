"""Text to speech."""

from __future__ import annotations

import io
import wave
from pathlib import Path
from typing import Protocol

SAMPLE_RATE = 22050
WORDS_PER_SECOND = 2.6
"""Conversational VO pace, shared with the script node."""


class BackendUnavailable(RuntimeError):
    """Raised when a backend's model or dependency is not installed."""


class SpeechBackend(Protocol):
    name: str
    model: str

    def estimate_duration(self, text: str) -> float: ...
    def synthesize(self, text: str) -> bytes: ...


def wav_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def _silence(duration_s: float) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        handle.writeframes(b"\x00\x00" * int(duration_s * SAMPLE_RATE))
    return buffer.getvalue()


class NullSpeech:
    """Silent track of the right length.

    Not a stand-in for a voice — it is a *timing* stand-in, so the rest of the
    pipeline (durations, scene boundaries, caption windows) can be built and
    tested without a GPU. Provenance records it as `null` so no render can
    claim it was ever spoken.
    """

    name = "null"
    model = "silence"

    def estimate_duration(self, text: str) -> float:
        return round(max(1.0, len(text.split()) / WORDS_PER_SECOND), 3)

    def synthesize(self, text: str) -> bytes:
        return _silence(self.estimate_duration(text))


class _UninstalledSpeech:
    """A real backend that is not available in this environment."""

    def __init__(self, name: str, model: str, install: str) -> None:
        self.name = name
        self.model = model
        self._install = install

    def estimate_duration(self, text: str) -> float:
        return round(max(1.0, len(text.split()) / WORDS_PER_SECOND), 3)

    def synthesize(self, text: str) -> bytes:
        raise BackendUnavailable(
            f"speech backend {self.name!r} is not installed in this environment. "
            f"Install it with: {self._install}"
        )


def _kokoro() -> SpeechBackend:
    """Apache-2.0, 82M params, faster than real time on CPU. Draft voice."""
    return _UninstalledSpeech("kokoro", "kokoro-82M", "pip install kokoro>=0.9 soundfile")


def _chatterbox() -> SpeechBackend:
    """MIT, Resemble AI. Final voice."""
    return _UninstalledSpeech("chatterbox", "chatterbox-turbo", "pip install chatterbox-tts")


SPEECH_BACKENDS = {
    "null": NullSpeech,
    "kokoro": _kokoro,
    "chatterbox": _chatterbox,
}


def get_speech_backend(name: str) -> SpeechBackend:
    try:
        return SPEECH_BACKENDS[name]()
    except KeyError:
        raise KeyError(
            f"unknown speech backend {name!r}; expected one of {', '.join(SPEECH_BACKENDS)}"
        ) from None
