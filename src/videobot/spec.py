"""Scene spec validation.

The schema catches shape errors; the checks below catch the ones that would
still render — a title that exits before it enters, a scene gap that shows as
black, an uncited health claim. Those are the expensive kind.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema_util import load_schema, schema_errors

EPS = 1e-3
"""Float tolerance, ~1ms. Timings are authored in ms and stored in seconds."""


class SpecError(ValueError):
    """Raised by `validate` when a spec would not render correctly."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        joined = "\n  - ".join(errors)
        super().__init__(f"scene spec is invalid:\n  - {joined}")


def _check_timeline(spec: dict[str, Any], errors: list[str]) -> None:
    """Scenes must tile the timeline exactly: no overlaps, no gaps."""
    scenes = spec["scenes"]
    duration = spec["meta"]["duration_s"]

    seen: set[str] = set()
    for scene in scenes:
        if scene["id"] in seen:
            errors.append(f"scenes: duplicate scene id {scene['id']!r}")
        seen.add(scene["id"])
        if scene["out"] - scene["in"] <= EPS:
            errors.append(f"scene {scene['id']!r}: out ({scene['out']}) must be after in ({scene['in']})")

    if abs(scenes[0]["in"]) > EPS:
        errors.append(f"scene {scenes[0]['id']!r}: first scene must start at 0, not {scenes[0]['in']}")

    for current, following in zip(scenes, scenes[1:]):
        if abs(current["out"] - following["in"]) > EPS:
            errors.append(
                f"scene {following['id']!r}: starts at {following['in']} but "
                f"{current['id']!r} ends at {current['out']} — timeline must be contiguous"
            )

    if abs(scenes[-1]["out"] - duration) > EPS:
        errors.append(
            f"scene {scenes[-1]['id']!r}: ends at {scenes[-1]['out']} but "
            f"meta.duration_s is {duration}"
        )


def _check_elements(spec: dict[str, Any], errors: list[str]) -> None:
    """Every animation must begin and end inside its own scene."""
    citation_ids = {c["id"] for c in spec["citations"]}

    for scene in spec["scenes"]:
        seen: set[str] = set()
        for element in scene["elements"]:
            eid = f"{scene['id']}/{element['id']}"
            if element["id"] in seen:
                errors.append(f"scene {scene['id']!r}: duplicate element id {element['id']!r}")
            seen.add(element["id"])

            enter = element["in"]
            enter_end = enter["at"] + enter["dur"]
            if enter["at"] < scene["in"] - EPS:
                errors.append(f"{eid}: enters at {enter['at']}, before scene start {scene['in']}")
            if enter_end > scene["out"] + EPS:
                errors.append(f"{eid}: entrance ends at {enter_end}, after scene end {scene['out']}")

            leave = element.get("out")
            if leave is not None:
                if leave["at"] < enter_end - EPS:
                    errors.append(
                        f"{eid}: exits at {leave['at']} before its entrance completes at {enter_end}"
                    )
                if leave["at"] + leave["dur"] > scene["out"] + EPS:
                    errors.append(
                        f"{eid}: exit ends at {leave['at'] + leave['dur']}, "
                        f"after scene end {scene['out']}"
                    )

            for phase in ("in", "out"):
                transition = element.get(phase)
                if transition and transition["ease"].strip().lower() == "linear":
                    errors.append(
                        f"{eid}: {phase} uses linear easing — banned by the motion "
                        f"contract (UPGRADE-PLAN §5.1)"
                    )

            cite = element.get("cite")
            if cite is not None and cite not in citation_ids:
                errors.append(f"{eid}: cites unknown citation {cite!r}")


def _check_audio(spec: dict[str, Any], errors: list[str]) -> None:
    duration = spec["meta"]["duration_s"]
    beats = spec["audio"]["beats"]

    if any(later < earlier for earlier, later in zip(beats, beats[1:])):
        errors.append("audio.beats: must be sorted ascending")
    for beat in beats:
        if beat > duration + EPS:
            errors.append(f"audio.beats: {beat} lies past meta.duration_s ({duration})")
            break

    previous_end = 0.0
    for index, word in enumerate(spec["audio"]["words"]):
        if word["t1"] <= word["t0"]:
            errors.append(f"audio.words[{index}] ({word['w']!r}): t1 must be after t0")
        if word["t0"] < previous_end - EPS:
            errors.append(f"audio.words[{index}] ({word['w']!r}): overlaps the previous word")
        if word["t1"] > duration + EPS:
            errors.append(f"audio.words[{index}] ({word['w']!r}): ends past meta.duration_s")
        previous_end = max(previous_end, word["t1"])


def _check_compliance(spec: dict[str, Any], errors: list[str]) -> None:
    """The health-content gate (UPGRADE-PLAN §7.1).

    Enforced from Phase 1 so no later stage can quietly publish an uncited
    claim: the pipeline refuses to mark itself passed while one exists.
    """
    seen: set[str] = set()
    for citation in spec["citations"]:
        if citation["id"] in seen:
            errors.append(f"citations: duplicate citation id {citation['id']!r}")
        seen.add(citation["id"])

    unverified = [c["id"] for c in spec["citations"] if not c["verified"]]
    if spec["compliance"]["gate"] == "passed" and unverified:
        errors.append(
            "compliance.gate is 'passed' but these citations are unverified: "
            + ", ".join(sorted(unverified))
        )


def validate(spec: dict[str, Any]) -> None:
    """Raise `SpecError` listing everything wrong with `spec`."""
    errors = schema_errors(spec, load_schema("scene-spec"))
    if errors:
        # Semantic checks index into the spec freely; running them on a
        # structurally broken document produces noise, not information.
        raise SpecError(errors)

    _check_timeline(spec, errors)
    _check_elements(spec, errors)
    _check_audio(spec, errors)
    _check_compliance(spec, errors)
    if errors:
        raise SpecError(errors)


def lint(spec: dict[str, Any]) -> list[str]:
    """Non-fatal craft warnings — things that render but read as amateur."""
    warnings: list[str] = []
    meta = spec["meta"]

    if meta["aspect"] == "9:16" and meta["duration_s"] > 55:
        warnings.append(
            f"meta.duration_s is {meta['duration_s']}s; keep vertical cuts under 55s "
            f"so the platform does not truncate the tail"
        )

    for scene in spec["scenes"]:
        length = scene["out"] - scene["in"]
        if length < 1.2:
            warnings.append(f"scene {scene['id']!r} is {length:.2f}s — too short to read")

        entrances = sorted(e["in"]["at"] for e in scene["elements"])
        for earlier, later in zip(entrances, entrances[1:]):
            if abs(later - earlier) < 0.04:
                warnings.append(
                    f"scene {scene['id']!r}: elements enter {abs(later - earlier) * 1000:.0f}ms "
                    f"apart — stagger by ~75ms so it reads as choreography, not a slide"
                )
                break

        for element in scene["elements"]:
            dur = element["in"]["dur"]
            if not 0.2 <= dur <= 0.8:
                warnings.append(
                    f"scene {scene['id']!r}/{element['id']!r}: entrance is {dur:.2f}s "
                    f"(expected 0.20-0.80s)"
                )

    if not any(scene["layout"] == "statement-card" for scene in spec["scenes"]):
        warnings.append(
            "no claim cards — a hook and an end card with nothing between them is not a video"
        )
    if not spec["audio"]["words"]:
        warnings.append("audio.words is empty — captions cannot be generated without alignment")
    if spec["compliance"]["gate"] != "passed":
        warnings.append(
            f"compliance.gate is {spec['compliance']['gate']!r} — not publishable until passed "
            f"and signed off by a human"
        )
    return warnings


def dumps(spec: dict[str, Any]) -> str:
    return json.dumps(spec, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def write(spec: dict[str, Any], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dumps(spec), "utf-8")
    return path


def read(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text("utf-8"))
