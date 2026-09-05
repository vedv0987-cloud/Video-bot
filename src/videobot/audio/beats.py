"""Beat map — where cuts and entrances land (UPGRADE-PLAN §5.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

DEFAULT_BPM = 92
"""Unhurried but forward-moving; suits explanatory health content."""


@dataclass(frozen=True)
class BeatMap:
    method: str
    bpm: float
    beats: list[float]


class BeatSource(Protocol):
    method: str

    def beats(self, duration_s: float) -> BeatMap: ...


class FixedTempoBeats:
    """A metronome grid.

    With generated music the tempo is chosen rather than discovered, so a grid
    is not an approximation of the truth — it *is* the truth, provided the
    music node is later told to render at the same BPM.
    """

    method = "fixed-tempo"

    def __init__(self, bpm: float = DEFAULT_BPM) -> None:
        self.bpm = bpm

    def beats(self, duration_s: float) -> BeatMap:
        interval = 60.0 / self.bpm
        count = int(duration_s / interval) + 1
        return BeatMap(self.method, self.bpm, [round(i * interval, 3) for i in range(count)])


class LibrosaBeats:
    """Onset detection against a real track.

    Declared, not written: there is no real track to analyse until the music
    node lands in Phase 4, and onset detection on a voiceover finds syllables,
    not beats.
    """

    method = "librosa"

    def __init__(self, bpm: float = DEFAULT_BPM) -> None:
        self.bpm = bpm

    def beats(self, duration_s: float) -> BeatMap:
        from .speech import BackendNotImplemented

        raise BackendNotImplemented(
            "beat source 'librosa' has no implementation yet — onset detection needs a music "
            "track, which the pipeline does not produce until Phase 4. Use --beats fixed-tempo."
        )


BEAT_SOURCES = {"fixed-tempo": FixedTempoBeats, "librosa": LibrosaBeats}


def get_beat_source(name: str, bpm: float = DEFAULT_BPM) -> BeatSource:
    try:
        return BEAT_SOURCES[name](bpm)
    except KeyError:
        raise KeyError(
            f"unknown beat source {name!r}; expected one of {', '.join(BEAT_SOURCES)}"
        ) from None
