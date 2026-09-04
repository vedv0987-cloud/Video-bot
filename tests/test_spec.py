from __future__ import annotations

import pytest

from videobot import spec as spec_mod


def expect_error(spec, fragment):
    with pytest.raises(spec_mod.SpecError) as excinfo:
        spec_mod.validate(spec)
    assert any(fragment in message for message in excinfo.value.errors), excinfo.value.errors


def test_minimal_spec_is_valid(spec):
    spec_mod.validate(spec)


def test_schema_violation_is_reported(spec):
    spec["meta"]["aspect"] = "4:3"
    expect_error(spec, "aspect")


def test_unknown_key_is_rejected(spec):
    """additionalProperties:false is what catches a typo before it renders."""
    spec["scenes"][0]["elements"][0]["contnet"] = "typo"
    expect_error(spec, "contnet")


def test_gap_in_timeline_is_rejected(spec):
    spec["scenes"][0]["out"] = 2.0
    spec["scenes"][0]["elements"][0]["out"] = {
        "at": 1.4, "anim": "fade-scale", "ease": "cubic.in", "dur": 0.22,
    }
    spec["scenes"].append(
        {
            "id": "second", "in": 2.5, "out": 4.0, "tier": "A", "layout": "end-card",
            "bg": {"type": "solid"}, "elements": [],
        }
    )
    expect_error(spec, "contiguous")


def test_last_scene_must_reach_declared_duration(spec):
    spec["meta"]["duration_s"] = 9.0
    expect_error(spec, "meta.duration_s is 9.0")


def test_first_scene_must_start_at_zero(spec):
    spec["scenes"][0]["in"] = 0.5
    expect_error(spec, "must start at 0")


def test_element_cannot_exit_before_it_enters(spec):
    spec["scenes"][0]["elements"][0]["out"]["at"] = 0.5
    expect_error(spec, "before its entrance completes")


def test_element_cannot_animate_past_its_scene(spec):
    spec["scenes"][0]["elements"][0]["out"]["at"] = 3.9
    expect_error(spec, "after scene end")


def test_linear_easing_is_banned(spec):
    spec["scenes"][0]["elements"][0]["in"]["ease"] = "linear"
    expect_error(spec, "linear easing")


def test_duplicate_element_ids_are_rejected(spec):
    spec["scenes"][0]["elements"].append(dict(spec["scenes"][0]["elements"][0]))
    expect_error(spec, "duplicate element id")


def test_dangling_citation_reference_is_rejected(spec):
    spec["scenes"][0]["elements"][0]["cite"] = "ghost"
    expect_error(spec, "unknown citation")


def test_unsorted_beats_are_rejected(spec):
    spec["audio"]["beats"] = [1.0, 0.5]
    expect_error(spec, "sorted ascending")


def test_beats_past_the_end_are_rejected(spec):
    spec["audio"]["beats"] = [0.5, 99.0]
    expect_error(spec, "past meta.duration_s")


def test_overlapping_words_are_rejected(spec):
    spec["audio"]["words"] = [
        {"w": "you", "t0": 0.3, "t1": 0.9},
        {"w": "are", "t0": 0.5, "t1": 1.1},
    ]
    expect_error(spec, "overlaps the previous word")


def test_gate_cannot_pass_with_unverified_claims(spec):
    """The health-content gate (UPGRADE-PLAN §7.1) is enforced structurally."""
    spec["citations"] = [
        {"id": "c1", "claim": "60% water", "source": "PMID:1", "verified": False},
    ]
    spec["compliance"]["gate"] = "passed"
    expect_error(spec, "unverified")


def test_gate_may_pass_when_every_claim_is_verified(spec):
    spec["citations"] = [
        {"id": "c1", "claim": "60% water", "source": "PMID:1", "verified": True},
    ]
    spec["compliance"]["gate"] = "passed"
    spec_mod.validate(spec)


def test_lint_flags_pending_gate_and_missing_alignment(spec):
    warnings = spec_mod.lint(spec)
    assert any("compliance.gate" in w for w in warnings)
    assert any("audio.words is empty" in w for w in warnings)


def test_lint_flags_overlong_vertical_cut(spec):
    spec["meta"]["duration_s"] = 70.0
    spec["scenes"][0]["out"] = 70.0
    assert any("under 55s" in w for w in spec_mod.lint(spec))


def test_lint_flags_simultaneous_entrances(spec):
    twin = dict(spec["scenes"][0]["elements"][0])
    twin["id"] = "twin"
    spec["scenes"][0]["elements"].append(twin)
    assert any("stagger" in w for w in spec_mod.lint(spec))


def test_roundtrip_write_and_read(spec, tmp_path):
    path = spec_mod.write(spec, tmp_path / "nested" / "scene-spec.json")
    assert spec_mod.read(path) == spec
