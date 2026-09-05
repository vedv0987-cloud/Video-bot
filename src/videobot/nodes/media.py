"""Media node — licensed stills for the scenes that can use one.

Imagery is opportunistic on purpose. The freely-licensed pool for health
topics is largely clinical documentation, and forcing a picture into every
scene makes the cut worse, not better. So this node attaches an image only
when one clears the licence, subject and shape filters, and leaves the scene
to its procedural background otherwise.

Images are written into the cache beside the manifest and referenced by
content digest, so a re-run with unchanged inputs reuses the same files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from ..cache import Artifact
from ..dag import Node
from ..hashing import digest_bytes
from ..http import FetchError, get_bytes
from ..sources.commons import CommonsImageSource
from ..sources.footage import LocalFootageSource, PexelsVideoSource, probe_clip

MAX_IMAGES = 3
"""More than a few stills in a 30-second cut starts to look like a slideshow
of someone else's photographs rather than a designed piece."""

MOVES = ("ken-burns-in", "pan-left", "ken-burns-out", "pan-right")

MAX_CLIPS = 4
"""Footage is the visual language when it is present, so more scenes may carry
a clip than may carry a still — but a cut that changes picture every two
seconds reads as a trailer, not an explainer."""


def footage_source(ctx: Mapping[str, Any]):
    """The footage backend this run asked for, or None."""
    choice = ctx.get("footage")
    if not choice:
        return None
    if choice == "pexels":
        return PexelsVideoSource()
    return LocalFootageSource(choice)


def queries(topic: str) -> list[str]:
    """Search terms, broad to narrow.

    Building a query from each claim's own words sounded principled and was
    useless in practice: it produced things like "dehydration occurs exceeds
    intake", because the long words in a sentence are usually verbs. Searching
    the topic and widening once is both simpler and better.
    """
    return [topic, f"{topic} water", "drinking water glass"]


class MediaNode(Node):
    name = "media"
    version = "2"
    deps = ("script",)
    suffix = ".json"

    def params(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        # The source's version rides in the key for the same reason the
        # research node carries its sources': changing how media is chosen
        # must not leave a warm cache serving the old choices.
        footage = footage_source(ctx)
        return {
            "topic": ctx["topic"],
            "enabled": ctx["media"],
            "source": f"{CommonsImageSource.kind}@{CommonsImageSource.version}",
            "footage": (
                f"{footage.kind}@{footage.version}:{ctx['footage']}" if footage else None
            ),
        }

    def produce(self, ctx: Mapping[str, Any], inputs: Mapping[str, Artifact]) -> bytes:
        script = inputs["script"].read_json()
        store = ctx["cache_root"] / "media"

        # Footage first: when there is real motion under the type, stills are
        # not wanted as well — two picture systems in one cut look like an
        # accident rather than a choice.
        footage = footage_source(ctx)
        if footage is not None:
            store.mkdir(parents=True, exist_ok=True)
            return _footage_manifest(footage, script, store)

        if not ctx["media"]:
            return json.dumps({"images": {}, "notes": ["media disabled"]}, indent=2).encode()

        source = CommonsImageSource()
        store.mkdir(parents=True, exist_ok=True)

        images: dict[str, Any] = {}
        notes: list[str] = []

        # One search, widened only if it comes up short — rather than a search
        # per scene, which returns the same picture repeatedly anyway.
        found: list[Any] = []
        seen: set[str] = set()
        for query in queries(script["topic"]):
            if len(found) >= MAX_IMAGES:
                break
            try:
                for picture in source.fetch(query, MAX_IMAGES):
                    if picture.url not in seen:
                        seen.add(picture.url)
                        found.append(picture)
            except FetchError as exc:
                notes.append(f"search {query!r} failed — {exc}")

        if not found:
            notes.append("no image cleared the licence, subject and shape filters")

        points = [s for s in script["sections"] if s["kind"] == "point"][:MAX_IMAGES]
        for index, (section, picture) in enumerate(zip(points, found)):
            try:
                payload = get_bytes(picture.url)
            except FetchError as exc:
                notes.append(f"{section['id']}: download failed — {exc}")
                continue

            digest = digest_bytes(payload)
            path = store / f"{digest}.jpg"
            if not path.exists():
                path.write_bytes(payload)

            images[section["id"]] = {
                "kind": "image",
                "src": str(path),
                "url": picture.url,
                "credit": picture.credit,
                "licence": picture.licence,
                "page": picture.page,
                "treatment": {
                    # Alternate the move so consecutive stills do not drift
                    # the same way, which reads as a template.
                    "move": MOVES[index % len(MOVES)],
                    "scale_from": 1.06 if index % 2 == 0 else 1.18,
                    "scale_to": 1.18 if index % 2 == 0 else 1.06,
                },
            }

        return json.dumps({"images": images, "notes": notes}, indent=2, ensure_ascii=False).encode()


def _footage_manifest(source: Any, script: Mapping[str, Any], store: Path) -> bytes:
    """Clips for the scenes that can carry one.

    A source failure is recorded and the run continues on procedural
    backgrounds — a missing key should cost you the footage, not the video.
    """
    images: dict[str, Any] = {}
    notes: list[str] = []
    clips: list[Any] = []

    for query in queries(script["topic"]):
        if len(clips) >= MAX_CLIPS:
            break
        try:
            clips.extend(source.fetch(query, MAX_CLIPS))
        except FetchError as exc:
            notes.append(f"footage search {query!r} failed — {exc}")
            break  # a key that is missing for one query is missing for all

    points = [s for s in script["sections"] if s["kind"] == "point"][:MAX_CLIPS]
    for index, (section, clip) in enumerate(zip(points, clips)):
        try:
            path = _stage(clip, store)
            duration = clip.duration_s or probe_clip(path)
        except (FetchError, OSError, RuntimeError) as exc:
            notes.append(f"{section['id']}: clip unusable — {exc}")
            continue

        images[section["id"]] = {
            "kind": "video",
            "src": str(path),
            "credit": clip.credit,
            "licence": clip.licence,
            "page": clip.page,
            "duration_s": round(duration, 3),
            "treatment": {
                "move": MOVES[index % len(MOVES)],
                "scale_from": 1.0 if index % 2 == 0 else 1.12,
                "scale_to": 1.12 if index % 2 == 0 else 1.0,
            },
        }

    if not images and not notes:
        notes.append("no footage cleared the size and length filters")
    return json.dumps({"images": images, "notes": notes}, indent=2, ensure_ascii=False).encode()


def _stage(clip: Any, store: Path) -> Path:
    """Local clips stay where they are; remote ones land in the cache by digest."""
    if clip.local:
        return Path(clip.src)

    payload = get_bytes(clip.src)
    path = store / f"{digest_bytes(payload)}.mp4"
    if not path.exists():
        path.write_bytes(payload)
    return path
