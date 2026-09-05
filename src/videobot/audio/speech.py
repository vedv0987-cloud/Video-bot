"""Text to speech."""

from __future__ import annotations

import array
import io
import re
import sys
import wave
from pathlib import Path
from typing import Any, Iterable, Iterator, Protocol, Sequence

SAMPLE_RATE = 22050
WORDS_PER_SECOND = 2.6
"""Conversational VO pace, shared with the script node."""

KOKORO_REPO = "hexgrad/Kokoro-82M"
KOKORO_SAMPLE_RATE = 24000
KOKORO_VOICE = "af_heart"
KOKORO_CHUNK_CHARS = 350
"""Kokoro truncates past 510 phoneme tokens with only a warning on stderr, so a
long script would lose its tail silently. 350 characters of English is well
inside that ceiling with room for dense phonemes."""

CHUNK_GAP_S = 0.12
"""A beat between chunks. Sentences synthesised in isolation butt together with
no breath at all, which is the single most obvious tell of machine narration."""

KOKORO_SEED = 0
"""Kokoro samples. Measured: two runs of the same sentence differ across 78% of
their samples, by up to 9% of full scale — audible, and enough to rewrite the
voice artifact on every run and invalidate align, beats and compose behind it.
Seeded, the wav is a pure function of the script (invariant 1)."""


class BackendUnavailable(RuntimeError):
    """Raised when a backend's model or dependency is not installed."""


class BackendNotImplemented(BackendUnavailable):
    """Raised when a backend is named in the plan but has no code behind it.

    Distinct from `BackendUnavailable` because the remedy is different: no
    amount of installing fixes it. Telling someone to `pip install` a backend
    that was never written wastes an afternoon and a few gigabytes.
    """


class SpeechBackend(Protocol):
    name: str
    model: str

    def estimate_duration(self, text: str) -> float: ...
    def synthesize(self, text: str) -> bytes: ...


def wav_duration(path: str | Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def pcm16(samples: Iterable[float]) -> bytes:
    """Float samples in [-1, 1] to little-endian 16-bit PCM.

    Takes anything iterable — a list, a numpy array, a torch tensor — so the
    conversion stays testable in an environment with no model stack installed.
    """
    values = samples.tolist() if hasattr(samples, "tolist") else list(samples)
    frames = array.array("h", (int(round(max(-1.0, min(1.0, v)) * 32767)) for v in values))
    if sys.byteorder == "big":
        frames.byteswap()
    return frames.tobytes()


def _wav(frames: bytes, sample_rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(frames)
    return buffer.getvalue()


def _silence(duration_s: float) -> bytes:
    return _wav(b"\x00\x00" * int(duration_s * SAMPLE_RATE), SAMPLE_RATE)


_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_CLAUSE = re.compile(r"(?<=[,;:])\s+")


def chunk_text(text: str, limit: int = KOKORO_CHUNK_CHARS) -> list[str]:
    """Sentence groups short enough to survive the model's context window.

    Splits on sentence ends first, falling back to clause boundaries for a
    sentence that is on its own too long. Pure function of the text: the same
    script always chunks the same way, so the voice artifact stays cacheable.
    """
    chunks: list[str] = []
    current = ""
    for sentence in _sentences(text.strip(), limit):
        if current and len(current) + 1 + len(sentence) > limit:
            chunks.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current)
    return chunks


def _sentences(text: str, limit: int) -> Iterator[str]:
    for sentence in _SENTENCE.split(text):
        if not sentence:
            continue
        if len(sentence) <= limit:
            yield sentence
            continue
        # One sentence over the ceiling. Clauses are the next natural seam;
        # a sentence with no clause breaks at all is passed through whole
        # rather than cut mid-word.
        for clause in _CLAUSE.split(sentence):
            if clause:
                yield clause


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


class KokoroSpeech:
    """Kokoro-82M (Apache-2.0) — faster than real time on CPU. The draft voice.

    The pipeline is built on first use, not in `__init__`: the voice node
    constructs a backend just to read its name and model into the cache key,
    and that must not pull 300 MB of weights.
    """

    name = "kokoro"
    install = "pip install kokoro>=0.9 soundfile"

    def __init__(
        self, voice: str = KOKORO_VOICE, lang_code: str = "a", seed: int = KOKORO_SEED
    ) -> None:
        self.voice = voice
        self.lang_code = lang_code
        self.seed = seed
        # The seed belongs in the model id because the voice node hashes this
        # string into the cache key: changing the seed changes the audio.
        self.model = f"kokoro-82M:{voice}@{seed}"
        self._pipeline: Any = None
        self._torch: Any = None

    def estimate_duration(self, text: str) -> float:
        return round(max(1.0, len(text.split()) / WORDS_PER_SECOND), 3)

    def _load(self) -> Any:
        if self._pipeline is None:
            try:
                import torch

                from kokoro import KPipeline
            except ImportError as exc:
                raise BackendUnavailable(
                    f"speech backend {self.name!r} is not installed in this environment. "
                    f"Install it with: {self.install}"
                ) from exc
            try:
                self._pipeline = KPipeline(lang_code=self.lang_code, repo_id=KOKORO_REPO)
            except TypeError:  # repo_id arrived in kokoro 0.9.4
                self._pipeline = KPipeline(lang_code=self.lang_code)
            self._torch = torch
        return self._pipeline

    def synthesize(self, text: str) -> bytes:
        pipeline = self._load()
        gap = b"\x00\x00" * int(CHUNK_GAP_S * KOKORO_SAMPLE_RATE)

        parts: list[bytes] = []
        for chunk in chunk_text(text):
            # Per chunk, not once per call: a chunk's audio then depends only on
            # its own text, so re-chunking a script leaves untouched chunks
            # byte-identical.
            self._torch.manual_seed(self.seed)
            spoken = b"".join(
                pcm16(audio) for audio in _kokoro_audio(pipeline(chunk, voice=self.voice))
            )
            if spoken:
                parts.append(spoken)
        if not parts:
            raise BackendUnavailable(
                f"speech backend {self.name!r} produced no audio for {len(text)} characters "
                "of script — the model loaded but returned nothing"
            )
        return _wav(gap.join(parts), KOKORO_SAMPLE_RATE)


def _kokoro_audio(results: Iterable[Any]) -> Iterator[Sequence[float]]:
    """Audio out of a KPipeline generator, across its two result shapes.

    Older kokoro yields `(graphemes, phonemes, audio)` tuples; 0.9+ yields a
    `Result` object. Both appear in the wild depending on what pip resolves.
    """
    for result in results:
        audio = result[2] if isinstance(result, tuple) else getattr(result, "audio", None)
        if audio is not None:
            yield audio


class _PlannedSpeech:
    """A voice the plan names and nothing implements yet."""

    def __init__(self, name: str, model: str, why: str) -> None:
        self.name = name
        self.model = model
        self._why = why

    def estimate_duration(self, text: str) -> float:
        return round(max(1.0, len(text.split()) / WORDS_PER_SECOND), 3)

    def synthesize(self, text: str) -> bytes:
        raise BackendNotImplemented(
            f"speech backend {self.name!r} has no implementation yet — {self._why}. "
            "Use --voice kokoro for a real voice, or --voice null for a silent timing track."
        )


def _chatterbox() -> SpeechBackend:
    """MIT, Resemble AI. Final voice."""
    return _PlannedSpeech(
        "chatterbox",
        "chatterbox-turbo",
        "it is the Phase 4 finishing voice and Kokoro carries drafts until then",
    )


SPEECH_BACKENDS = {
    "null": NullSpeech,
    "kokoro": KokoroSpeech,
    "chatterbox": _chatterbox,
}


def get_speech_backend(name: str) -> SpeechBackend:
    try:
        return SPEECH_BACKENDS[name]()
    except KeyError:
        raise KeyError(
            f"unknown speech backend {name!r}; expected one of {', '.join(SPEECH_BACKENDS)}"
        ) from None
