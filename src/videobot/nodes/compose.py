"""Compose node — turns a script into a scene spec.

This is the node that encodes the motion contract: every timing it emits comes
from the brand tokens, so retiming the house style is a token edit rather than
a code change (UPGRADE-PLAN §5.1, §5.8).
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from ..brand import Brand
from ..cache import Artifact
from ..dag import Node
from ..hashing import digest_data
from ..platforms import get_format
from .script import WORDS_PER_SECOND

MIN_SCENE_S = 2.2
"""Below this a viewer cannot read the card, however good the animation."""

SCENE_PAD_S = 0.9
"""Breath either side of the spoken line, so cuts do not clip the voice."""

ENTER_LEAD_S = 0.35
"""Delay before the first element lands — a beat of empty frame reads as poise."""

EXIT_LEAD_S = 0.30
"""How far before the cut the exit begins."""


def _round(value: float) -> float:
    """3dp keeps the timeline exactly contiguous under float addition."""
    return round(value + 0.0, 3)


def _scene_length(words: int) -> float:
    return _round(max(MIN_SCENE_S, words / WORDS_PER_SECOND + SCENE_PAD_S))


class ComposeNode(Node):
    name = "compose"
    version = "1"
    deps = ("script",)
    suffix = ".json"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        brand: Brand = ctx["brand"]
        return {
            "aspect": ctx["aspect"],
            "slug": ctx["slug"],
            "brand_id": brand.id,
            "brand_digest": brand.digest,
        }

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        brand: Brand = ctx["brand"]
        fmt = get_format(ctx["aspect"])
        script = inputs["script"].read_json()

        scenes: list[dict[str, Any]] = []
        cursor = 0.0
        for section in script["sections"]:
            length = _scene_length(section["words"])
            scene = self._scene(section, brand, start=cursor, length=length)
            scenes.append(scene)
            cursor = scene["out"]

        claims = {c["id"]: c for c in script["claims"]}
        citations = [
            {
                "id": claim_id,
                "claim": claim["text"],
                "source": claim["source"],
                "verified": claim["verified"],
            }
            for claim_id, claim in claims.items()
        ]
        unverified = [c["id"] for c in citations if not c["verified"]]

        spec = {
            "version": "1.0",
            "meta": {
                "topic": script["topic"],
                "slug": ctx["slug"],
                "duration_s": _round(cursor),
                "aspect": fmt.aspect,
                "fps": fmt.fps,
                "resolution": list(fmt.authoring),
            },
            "brand": brand.ref(),
            "audio": {"vo": None, "music": None, "beats": [], "words": []},
            "scenes": scenes,
            "captions": brand.captions_block(fmt.safe_area),
            "citations": citations,
            "compliance": {
                "gate": "passed" if not unverified else "pending",
                "requires_human_signoff": True,
                "notes": (
                    [f"{len(unverified)} unverified claim(s): {', '.join(unverified)}"]
                    if unverified
                    else []
                ),
            },
        }
        return json.dumps(spec, indent=2, ensure_ascii=False).encode("utf-8")

    def _scene(
        self, section: Mapping[str, Any], brand: Brand, *, start: float, length: float
    ) -> dict[str, Any]:
        out = _round(start + length)
        elements = self._elements(section, brand, start=start, out=out)
        return {
            "id": section["id"],
            "in": _round(start),
            "out": out,
            "tier": "A",
            "layout": {"hook": "statement-center", "list": "list-reveal", "cta": "end-card"}[
                section["kind"]
            ],
            "bg": {
                "type": "gradient-mesh",
                # Deterministic per scene: the same spec always renders the
                # same background, which is what makes renders reproducible.
                "seed": int(digest_data(section["id"])[:6], 16),
                "drift": 0.02,
            },
            "elements": elements,
        }

    def _elements(
        self, section: Mapping[str, Any], brand: Brand, *, start: float, out: float
    ) -> list[dict[str, Any]]:
        enter_dur = brand.duration_s("entrance")
        exit_dur = brand.duration_s("exit")
        stagger = brand.stagger_s
        exit_at = _round(out - EXIT_LEAD_S - exit_dur)

        def transitions(index: int) -> dict[str, Any]:
            return {
                "in": {
                    "at": _round(start + ENTER_LEAD_S + index * stagger),
                    "anim": "rise-blur",
                    "ease": brand.ease("entrance"),
                    "dur": enter_dur,
                    "snap": "none",
                },
                "out": {
                    "at": exit_at,
                    "anim": "fade-scale",
                    "ease": brand.ease("exit"),
                    "dur": exit_dur,
                    "snap": "none",
                },
            }

        role = {"hook": "display", "list": "headline", "cta": "headline"}[section["kind"]]
        elements: list[dict[str, Any]] = [
            {"type": "text", "id": "lead", "role": role, "content": section["text"], **transitions(0)}
        ]

        if section["kind"] == "list":
            items = section["items"]
            element: dict[str, Any] = {
                "type": "list",
                "id": "points",
                "role": "body",
                "items": items,
                "stagger_ms": brand.tokens["motion"]["stagger_ms"],
                **transitions(1),
            }
            # A list carries several claims; the spec cites one per element, so
            # attach the first and let Phase 2 split multi-claim lists.
            if section["cites"]:
                element["cite"] = section["cites"][0]
            elements.append(element)

        return elements
