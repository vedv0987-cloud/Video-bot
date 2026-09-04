"""Source protocol and evidence record."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence


@dataclass(frozen=True)
class Evidence:
    """One citable passage.

    `source_id` must be stable and resolvable — a PMID, or a Wikipedia revision
    id. "According to Wikipedia" is not a citation; a pinned revision is.
    """

    text: str
    source_id: str
    source_kind: str
    title: str
    url: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_id": self.source_id,
            "source_kind": self.source_kind,
            "title": self.title,
            "url": self.url,
        }


class Source(Protocol):
    """Anything that can turn a topic into citable passages."""

    kind: str

    def fetch(self, topic: str, limit: int) -> Sequence[Evidence]: ...


@dataclass(frozen=True)
class GatherResult:
    """What retrieval actually returned, including what it failed to return."""

    evidence: list[Evidence]
    failures: list[dict[str, str]]


@dataclass(frozen=True)
class SourceSet:
    """The sources a run may draw on, in priority order."""

    sources: tuple[Source, ...]

    def gather(self, topic: str, per_source: int) -> GatherResult:
        """Collect evidence from every source, recording any that failed.

        A dead source degrades the run rather than stopping it — but it is
        never silent. A transient outage that costs the only source of on-screen
        prose would otherwise produce a contentless video that still looks
        healthy, which is worse than an error.
        """
        collected: list[Evidence] = []
        failures: list[dict[str, str]] = []
        for source in self.sources:
            try:
                collected.extend(source.fetch(topic, per_source))
            except Exception as exc:  # noqa: BLE001 - a dead source must not be fatal
                failures.append({"source": source.kind, "error": f"{type(exc).__name__}: {exc}"})
        return GatherResult(collected, failures)

    def describe(self) -> list[str]:
        return [source.kind for source in self.sources]


def live_sources() -> SourceSet:
    """The default production source set."""
    from .pubmed import PubMedSource
    from .wikipedia import WikipediaSource

    return SourceSet((WikipediaSource(), PubMedSource()))
