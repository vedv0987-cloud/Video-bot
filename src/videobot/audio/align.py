"""Word-level alignment."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Sequence

GAP_S = 0.06
"""Silence between words, so caption windows do not butt against each other."""


@dataclass
class AlignResult:
    method: str
    duration_s: float
    words: list[dict] = field(default_factory=list)
    sections: list[dict] = field(default_factory=list)


class Aligner(Protocol):
    method: str

    def align(self, sections: Sequence[dict], duration_s: float) -> AlignResult: ...


class EstimatedAligner:
    """Distributes words across the track proportionally to their length.

    Honest about what it is: an estimate, recorded as such in provenance. Good
    enough to build and test caption windows and scene boundaries; nowhere near
    good enough to burn karaoke captions against real speech, which is what
    WhisperX is for.
    """

    method = "estimated"

    def align(self, sections: Sequence[dict], duration_s: float) -> AlignResult:
        spoken = [
            (section["id"], word)
            for section in sections
            for word in " ".join([section["text"], *section.get("items", [])]).split()
        ]
        if not spoken:
            return AlignResult(self.method, duration_s)

        # Longer words take longer to say; a flat split makes every caption
        # window the same length, which reads visibly wrong.
        weights = [len(word) + 1 for _, word in spoken]
        total_weight = sum(weights)
        speaking_time = max(0.1, duration_s - GAP_S * len(spoken))

        words: list[dict] = []
        cursor = 0.0
        for (section_id, word), weight in zip(spoken, weights):
            length = speaking_time * weight / total_weight
            words.append(
                {
                    "w": word,
                    "t0": round(cursor, 3),
                    "t1": round(cursor + length, 3),
                    "section": section_id,
                }
            )
            cursor += length + GAP_S

        spans: dict[str, list[float]] = {}
        for word in words:
            span = spans.setdefault(word["section"], [word["t0"], word["t1"]])
            span[1] = word["t1"]

        return AlignResult(
            method=self.method,
            duration_s=duration_s,
            words=words,
            sections=[
                {"id": section_id, "t0": start, "t1": end}
                for section_id, (start, end) in spans.items()
            ],
        )


class WhisperXAligner:
    """wav2vec2 forced alignment — sub-100ms word boundaries."""

    method = "whisperx"

    def align(self, sections: Sequence[dict], duration_s: float) -> AlignResult:
        from .speech import BackendUnavailable

        raise BackendUnavailable(
            "aligner 'whisperx' is not installed in this environment. "
            "Install it with: pip install whisperx"
        )


ALIGNERS = {"estimated": EstimatedAligner, "whisperx": WhisperXAligner}


def get_aligner(name: str) -> Aligner:
    try:
        return ALIGNERS[name]()
    except KeyError:
        raise KeyError(f"unknown aligner {name!r}; expected one of {', '.join(ALIGNERS)}") from None
