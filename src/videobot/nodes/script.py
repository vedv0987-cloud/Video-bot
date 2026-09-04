"""Script node — template-based, deterministic.

Phase 2 swaps the body for a constrained Qwen3 rewrite. The contract does not
change: claims in, structured script out, and the rewriter may never introduce
a claim that was not in its input (UPGRADE-PLAN §4.5).
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..cache import Artifact
from ..dag import Node

WORDS_PER_SECOND = 2.6
"""Conversational VO pace. ~100 words lands a 40s cut (UPGRADE-PLAN v1 §3)."""


def word_count(text: str) -> int:
    return len(text.split())


class ScriptNode(Node):
    name = "script"
    version = "1"
    deps = ("research",)
    suffix = ".json"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        return {"topic": ctx["topic"]}

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        research = inputs["research"].read_json()
        topic = research["topic"]
        claims = research["claims"]

        facts = [c for c in claims if c["kind"] == "fact"]
        prevention = [c for c in claims if c["kind"] == "prevention"]

        sections = [
            {
                "id": "hook",
                "kind": "hook",
                "text": f"What most people get wrong about {topic}.",
                "cites": [],
            },
            {
                "id": "facts",
                "kind": "list",
                "text": f"Three things worth knowing about {topic}:",
                "items": [c["text"] for c in facts],
                "cites": [c["id"] for c in facts],
            },
            {
                "id": "prevention",
                "kind": "list",
                "text": "What actually helps:",
                "items": [c["text"] for c in prevention],
                "cites": [c["id"] for c in prevention],
            },
            {
                "id": "cta",
                "kind": "cta",
                "text": "Follow for more evidence-based health explainers.",
                "cites": [],
            },
        ]

        for section in sections:
            spoken = " ".join([section["text"], *section.get("items", [])])
            section["words"] = word_count(spoken)

        payload = {
            "topic": topic,
            "sections": sections,
            "words": sum(s["words"] for s in sections),
            "claims": claims,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
