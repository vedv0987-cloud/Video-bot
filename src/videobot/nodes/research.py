"""Research node — live retrieval with citation capture.

Two things happen here that the rest of the pipeline depends on:

1. Every claim is bound to a pinned, resolvable source id before it can travel
   any further.
2. Every claim is screened against the blocked categories, and anything dropped
   is recorded with its reason rather than vanishing.

Retrieval is live, so a cache miss on a new day can return different text than
it did yesterday. That is inherent to citing a moving source; the cache means
it only happens when something upstream actually changed, and the pinned
revision id means an old spec still says exactly what it was built from.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..cache import Artifact
from ..dag import Node
from ..safety import is_citable, screen

PER_SOURCE = 5
"""Fetch a few more than needed — screening will reject some."""

DISPLAY_KINDS = {"wikipedia"}
"""Which sources may supply on-screen text.

Encyclopedia prose reads aloud; a paper's title does not. PubMed entries are
still captured as citations, they just are not put on a card.
"""


class ResearchNode(Node):
    name = "research"
    version = "3"
    deps = ()
    suffix = ".json"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "topic": ctx["topic"],
            "sources": ctx["sources"].describe(),
            "per_source": PER_SOURCE,
        }

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        topic = ctx["topic"]
        gathered = ctx["sources"].gather(topic, PER_SOURCE)

        claims: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for item in gathered.evidence:
            if not is_citable(item.source_id):
                rejected.append(
                    {"text": item.text, "category": "uncitable", "reason": "no resolvable source id"}
                )
                continue

            verdict = screen(item.text)
            if not verdict.allowed:
                rejected.append(
                    {"text": item.text, "category": verdict.category, "reason": verdict.reason}
                )
                continue

            claims.append(
                {
                    "id": f"c{len(claims) + 1}",
                    "text": item.text,
                    "source": item.source_id,
                    "source_kind": item.source_kind,
                    "title": item.title,
                    "url": item.url,
                    "display": item.source_kind in DISPLAY_KINDS,
                    # Verified means "traced to a pinned source", not "endorsed
                    # by a clinician" — hence the standing human sign-off.
                    "verified": True,
                }
            )

        payload = {
            "topic": topic,
            "claims": claims,
            "rejected": rejected,
            "source_failures": gathered.failures,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
