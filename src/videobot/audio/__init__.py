"""Audio backends.

Voice, alignment, and beat detection each sit behind a small interface with a
deterministic offline default. That is what lets the graph run anywhere while
the real models — Kokoro, Chatterbox-Turbo, WhisperX, librosa — drop in on a
machine that has a GPU, without the pipeline shape changing.

Every backend reports its identity into `audio.provenance` in the spec, so a
render always says how its timings were produced. Estimated alignment must
never be mistaken for measured alignment.
"""

from .align import ALIGNERS, AlignResult, get_aligner
from .beats import BEAT_SOURCES, get_beat_source
from .speech import SPEECH_BACKENDS, BackendUnavailable, get_speech_backend, wav_duration

__all__ = [
    "ALIGNERS",
    "AlignResult",
    "BEAT_SOURCES",
    "SPEECH_BACKENDS",
    "BackendUnavailable",
    "get_aligner",
    "get_beat_source",
    "get_speech_backend",
    "wav_duration",
]
