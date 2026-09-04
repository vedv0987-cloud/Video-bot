"""Research node — PLACEHOLDER until Phase 2.

Phase 2 replaces `produce` with Wikipedia + PubMed retrieval and real citation
capture. Until then it emits explicitly-marked placeholder claims: the pipeline
must never be able to mistake scaffolding for a verified medical fact, so every
claim here carries `verified: false`, which pins the compliance gate to
`pending` and blocks publication (UPGRADE-PLAN §7.1).
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..cache import Artifact
from ..dag import Node

PLACEHOLDER = "[PLACEHOLDER — Phase 2 will source and verify this claim]"

SECTIONS = ("fact", "fact", "fact", "prevention", "prevention")


class ResearchNode(Node):
    name = "research"
    version = "1"
    deps = ()
    suffix = ".json"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        return {"topic": ctx["topic"]}

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        topic = ctx["topic"]
        claims = [
            {
                "id": f"c{index + 1}",
                "kind": kind,
                "text": f"{PLACEHOLDER} {kind} #{index + 1} about {topic}.",
                "source": "unsourced",
                "verified": False,
            }
            for index, kind in enumerate(SECTIONS)
        ]
        payload = {"topic": topic, "claims": claims}
        return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
