"""Compose node — turns script, voice, alignment and beats into a scene spec.

Scene boundaries now come from where the voice actually lands rather than from
a word-count estimate, and every boundary is snapped to the beat grid when one
is close enough (UPGRADE-PLAN §5.4). All timings still originate in the brand
tokens, so retiming the house style stays a token edit.
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from ..audio.speech import get_speech_backend
from ..brand import Brand
from ..cache import Artifact
from ..dag import Node
from ..hashing import digest_data
from ..platforms import get_format

MIN_SCENE_S = 2.2
ENTER_LEAD_S = 0.35
EXIT_LEAD_S = 0.30
BEAT_SNAP_S = 0.12
"""Snap a cut to a beat only if it is already within 120ms of one — beyond
that, moving it would fight the voice rather than serve it."""

LAYOUTS = {"hook": "statement-center", "point": "statement-card", "cta": "end-card"}
ROLES = {"hook": "display", "point": "headline", "cta": "body"}

TRANSITION_S = 0.28
"""Long enough to register as a move, short enough not to cost a beat."""

BACKGROUNDS = ("gradient-mesh", "particle-field", "grid-lines")
"""Cycled across claim cards so five scenes do not read as one flat look. The
hook and the end card always take the gradient, which frames the piece."""


def _background(section: Mapping[str, Any], index: int) -> dict[str, Any]:
    kind = (
        "gradient-mesh"
        if section["kind"] != "point"
        else BACKGROUNDS[index % len(BACKGROUNDS)]
    )
    return {
        "type": kind,
        # Deterministic per scene: the same spec always renders the same
        # background, which is what makes renders reproducible.
        "seed": int(digest_data(section["id"])[:6], 16),
        "drift": 0.02,
        "density": 1.0,
    }


def _round(value: float) -> float:
    return round(value + 0.0, 3)


def _snap(value: float, beats: Sequence[float]) -> float:
    """Pull `value` onto the nearest beat within tolerance."""
    if not beats:
        return value
    nearest = min(beats, key=lambda beat: abs(beat - value))
    return nearest if abs(nearest - value) <= BEAT_SNAP_S else value


def scene_boundaries(
    sections: Sequence[Mapping[str, Any]], duration: float, beats: Sequence[float]
) -> list[float]:
    """Cut points between consecutive spoken sections.

    A cut lands in the silence between two sections, not on top of a word.
    Boundaries are then forced monotonic with a readable minimum, because a
    beat snap must never produce a scene too short to read.
    """
    boundaries = [0.0]
    for current, following in zip(sections, sections[1:]):
        midpoint = (current["t1"] + following["t0"]) / 2
        candidate = _snap(midpoint, beats)
        candidate = max(candidate, boundaries[-1] + MIN_SCENE_S)
        boundaries.append(_round(candidate))

    boundaries.append(_round(duration))

    # A late snap can push a boundary past the end; walk back from the tail.
    for index in range(len(boundaries) - 2, 0, -1):
        if boundaries[index] > boundaries[index + 1] - MIN_SCENE_S:
            boundaries[index] = _round(boundaries[index + 1] - MIN_SCENE_S)
    return boundaries


class ComposeNode(Node):
    name = "compose"
    version = "6"
    deps = ("script", "media", "voice", "align", "beats")
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
        alignment = inputs["align"].read_json()
        beat_map = inputs["beats"].read_json()
        media = inputs["media"].read_json()

        duration = alignment["duration_s"]
        beats = [beat for beat in beat_map["beats"] if beat <= duration]

        # Pair by id, not by index: a section that produced no words has no
        # span, and index-pairing would silently shift every later scene onto
        # the wrong boundary.
        spans = {section["id"]: section for section in alignment["sections"]}
        spoken = [section for section in script["sections"] if section["id"] in spans]
        boundaries = scene_boundaries([spans[s["id"]] for s in spoken], duration, beats)

        # Word indices per section, so the renderer can drive kinetic type and
        # captions from audio.words without re-deriving the alignment.
        ranges: dict[str, list[int]] = {}
        for position, word in enumerate(alignment["words"]):
            span = ranges.setdefault(word["section"], [position, position])
            span[1] = position

        scenes = [
            self._scene(
                section,
                brand,
                beats,
                start=boundaries[index],
                out=boundaries[index + 1],
                index=index,
                words=ranges.get(section["id"], [0, 0]),
                media=media["images"].get(section["id"]),
            )
            for index, section in enumerate(spoken)
        ]

        citations = [
            {
                "id": claim["id"],
                "claim": claim["text"],
                "source": claim["source"],
                "url": claim["url"],
                "verified": claim["verified"],
            }
            for claim in script["claims"]
        ]
        unverified = [c["id"] for c in citations if not c["verified"]]

        # A claim card is the only place a source reaches the viewer. Without
        # one the video says nothing sourced, however long the citation list is.
        claim_cards = sum(1 for section in script["sections"] if section["kind"] == "point")

        notes = [f"rewriter: {script['rewriter']}"]
        if script["rejected"]:
            notes.append(
                f"{len(script['rejected'])} passage(s) dropped by the safety screen: "
                + ", ".join(sorted({item["category"] for item in script["rejected"]}))
            )
        for note in media.get("notes", []):
            notes.append(f"media: {note}")
        for failure in script.get("source_failures", []):
            notes.append(f"source {failure['source']} failed: {failure['error']}")
        if unverified:
            notes.append(f"unverified claim(s): {', '.join(unverified)}")
        if not citations:
            notes.append("no citations retrieved — nothing on screen is sourced")
        if not claim_cards:
            notes.append("no claim cards — the cut carries no sourced content")

        backend = get_speech_backend(ctx["voice"])
        spec = {
            "version": "1.0",
            "meta": {
                "topic": script["topic"],
                "slug": ctx["slug"],
                "duration_s": _round(duration),
                "aspect": fmt.aspect,
                "fps": fmt.fps,
                "resolution": list(fmt.authoring),
                "safe_area": fmt.safe.as_dict(),
            },
            "brand": brand.ref(),
            "audio": {
                "vo": inputs["voice"].as_ref(),
                "music": None,
                "beats": beats,
                # `section` is alignment bookkeeping, not part of the spec's
                # word record; the schema rejects it.
                "words": [
                    {"w": word["w"], "t0": word["t0"], "t1": word["t1"]}
                    for word in alignment["words"]
                ],
                "provenance": {
                    "voice": {"backend": backend.name, "model": backend.model},
                    "alignment": {"method": alignment["method"]},
                    "beats": {"method": beat_map["method"], "bpm": beat_map["bpm"]},
                },
            },
            "scenes": scenes,
            "captions": brand.captions_block(fmt.safe_area),
            "citations": citations,
            "compliance": {
                "gate": (
                    "pending" if (unverified or not citations or not claim_cards) else "passed"
                ),
                "requires_human_signoff": True,
                "notes": notes,
            },
        }
        return json.dumps(spec, indent=2, ensure_ascii=False).encode("utf-8")

    def _scene(
        self,
        section: Mapping[str, Any],
        brand: Brand,
        beats: Sequence[float],
        *,
        start: float,
        out: float,
        index: int,
        words: Sequence[int],
        media: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        element = self._element(section, brand, beats, start=start, out=out)
        return {
            "id": section["id"],
            "in": _round(start),
            "out": _round(out),
            "tier": "A",
            "layout": LAYOUTS[section["kind"]],
            "bg": _background(section, index),
            "words": {"from": words[0], "to": words[1]},
            # The opening scene has nothing to transition from.
            "transition": {
                "type": "cut" if index == 0 else "dip",
                "dur": 0.0 if index == 0 else TRANSITION_S,
            },
            "media": self._media(media, out - start),
            "elements": [element],
        }

    @staticmethod
    def _media(media: Mapping[str, Any] | None, scene_s: float) -> dict[str, Any] | None:
        """Spec form of whatever the media node found for this scene."""
        if not media:
            return None

        block = {
            "kind": media["kind"],
            "src": media["src"],
            "credit": media["credit"],
            "licence": media["licence"],
            "page": media["page"],
            "treatment": media["treatment"],
        }
        if media["kind"] == "video":
            # The clip plays from its start for as long as the scene lasts. A
            # scene longer than its footage would freeze on the last frame, so
            # the span is clamped and the renderer loops what it is given.
            block["trim"] = {"from": 0.0, "to": round(min(scene_s, media["duration_s"]), 3)}
        return block

    def _element(
        self,
        section: Mapping[str, Any],
        brand: Brand,
        beats: Sequence[float],
        *,
        start: float,
        out: float,
    ) -> dict[str, Any]:
        enter_dur = brand.duration_s("entrance")
        exit_dur = brand.duration_s("exit")

        # Fit the lead-in to the scene: a short scene gets a shorter beat of
        # empty frame rather than an entrance that overruns its own cut.
        headroom = out - start - enter_dur - exit_dur - EXIT_LEAD_S
        lead = min(ENTER_LEAD_S, max(0.0, headroom * 0.5))
        enter_at = max(start, _snap(start + lead, beats))

        exit_at = out - EXIT_LEAD_S - exit_dur
        if exit_at < enter_at + enter_dur:
            exit_at = min(out - exit_dur, enter_at + enter_dur)

        element: dict[str, Any] = {
            "type": "text",
            "id": "lead",
            "role": ROLES[section["kind"]],
            "content": section["text"],
            "in": {
                "at": _round(enter_at),
                "anim": "rise-blur",
                "ease": brand.ease("entrance"),
                "dur": enter_dur,
                "snap": "beat" if beats else "none",
            },
            "out": {
                "at": _round(exit_at),
                "anim": "fade-scale",
                "ease": brand.ease("exit"),
                "dur": exit_dur,
                "snap": "none",
            },
        }
        # Only a claim card cites a source. The hook and the credit line are
        # connective text; pointing them at a paper would misrepresent what
        # that paper supports. Every reference still appears in `citations`.
        if section["kind"] == "point" and section["cites"]:
            element["cite"] = section["cites"][0]
        return element
