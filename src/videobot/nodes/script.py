"""Script node — assembles retrieved claims into a spoken structure.

The rewriter is swappable (a constrained Qwen3 pass replaces the template), but
`assert_no_invented_claims` runs against *any* backend's output. That check is
the actual safety property: a model may compress and connect, never introduce.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Protocol, Sequence

from ..cache import Artifact
from ..dag import Node

WORDS_PER_SECOND = 2.6

MAX_DISPLAY_CLAIMS = 3
"""Three cards is what fits a short before it stops being watchable."""

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


class InventedClaimError(ValueError):
    """Raised when a rewriter emits content its sources do not support."""


def assert_no_invented_claims(
    claims: Sequence[Mapping[str, Any]], sections: Sequence[Mapping[str, Any]]
) -> None:
    """Every cited id must exist, and every number must come from its source.

    The numeric check is the one that catches a hallucinating rewriter: models
    invent plausible statistics far more readily than they invent whole
    sentences.
    """
    known = {claim["id"]: claim["text"] for claim in claims}

    for section in sections:
        for cite in section.get("cites", []):
            if cite not in known:
                raise InventedClaimError(
                    f"section {section['id']!r} cites unknown claim {cite!r}"
                )

        supporting = " ".join(known[cite] for cite in section.get("cites", []))
        source_numbers = set(_NUMBER.findall(supporting))
        written = " ".join([section["text"], *section.get("items", [])])
        for number in _NUMBER.findall(written):
            if number not in source_numbers:
                raise InventedClaimError(
                    f"section {section['id']!r} states {number!r}, "
                    f"which none of its sources contain"
                )


class Rewriter(Protocol):
    name: str

    def sections(self, topic: str, claims: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]: ...


class TemplateRewriter:
    """Deterministic assembly, quoting sources verbatim.

    Verbatim is the conservative choice: nothing is paraphrased, so nothing can
    drift from what the source actually said.
    """

    name = "template"

    def sections(
        self, topic: str, claims: Sequence[Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        display = [claim for claim in claims if claim["display"]][:MAX_DISPLAY_CLAIMS]
        references = [claim for claim in claims if not claim["display"]]

        sections: list[dict[str, Any]] = [
            {
                "id": "hook",
                "kind": "hook",
                "text": f"Here is what the evidence says about {topic}.",
                "items": [],
                "cites": [],
            }
        ]

        for index, claim in enumerate(display, start=1):
            sections.append(
                {
                    "id": f"point-{index}",
                    "kind": "point",
                    "text": claim["text"],
                    "items": [],
                    "cites": [claim["id"]],
                }
            )

        # Deliberately digit-free: the numeric invariant treats any number in
        # script text as a claim needing a source, and a reference *count* is
        # pipeline bookkeeping, not something a source said. Keeping the rule
        # strict is worth more than keeping the tally.
        credit = (
            "Sourced from peer-reviewed research."
            if references
            else "Sources listed in the description."
        )
        sections.append(
            {
                "id": "cta",
                "kind": "cta",
                "text": f"{credit} Follow for more evidence-based health explainers.",
                "items": [],
                "cites": [claim["id"] for claim in references],
            }
        )
        return sections


class QwenRewriter:
    """Constrained local rewrite via Ollama (UPGRADE-PLAN §4.5)."""

    name = "qwen3"

    def sections(self, topic: str, claims: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        from ..audio.speech import BackendUnavailable

        raise BackendUnavailable(
            "rewriter 'qwen3' needs a local Ollama server. "
            "Install it from https://ollama.com then: ollama pull qwen3"
        )


REWRITERS = {"template": TemplateRewriter, "qwen3": QwenRewriter}


def get_rewriter(name: str) -> Rewriter:
    try:
        return REWRITERS[name]()
    except KeyError:
        raise KeyError(f"unknown rewriter {name!r}; expected one of {', '.join(REWRITERS)}") from None


def spoken_text(section: Mapping[str, Any]) -> str:
    return " ".join([section["text"], *section.get("items", [])])


class ScriptNode(Node):
    name = "script"
    version = "3"
    deps = ("research",)
    suffix = ".json"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        return {"rewriter": ctx["rewriter"]}

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        research = inputs["research"].read_json()
        rewriter = get_rewriter(ctx["rewriter"])

        sections = rewriter.sections(research["topic"], research["claims"])
        assert_no_invented_claims(research["claims"], sections)

        for section in sections:
            section["words"] = len(spoken_text(section).split())

        payload = {
            "topic": research["topic"],
            "rewriter": rewriter.name,
            "sections": sections,
            "words": sum(section["words"] for section in sections),
            "claims": research["claims"],
            "rejected": research["rejected"],
            "source_failures": research.get("source_failures", []),
        }
        return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
