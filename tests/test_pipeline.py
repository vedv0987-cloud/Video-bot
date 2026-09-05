from __future__ import annotations

import json
from pathlib import Path

import pytest

from videobot import spec as spec_mod
from videobot.brand import BrandError, load_brand
from videobot.cli import main, slugify
from videobot.platforms import get_format


BRAND_PATH = str(Path(__file__).resolve().parents[1] / "brand" / "health-v2.json")


# --- brand tokens ---------------------------------------------------------


def test_brand_loads_and_exposes_motion_tokens():
    brand = load_brand(BRAND_PATH)
    assert brand.id == "health-v2"
    assert brand.ease("entrance") == "expo.out"
    assert brand.duration_s("entrance") == pytest.approx(0.4)
    assert brand.stagger_s == pytest.approx(0.075)


def test_brand_digest_ignores_the_schema_pointer(tmp_path):
    """`$schema` is an editor affordance; it must not change the render's identity."""
    tokens = json.loads(Path(BRAND_PATH).read_text())
    without = tmp_path / "a.json"
    tokens.pop("$schema", None)
    without.write_text(json.dumps(tokens))
    assert load_brand(without).digest == load_brand(BRAND_PATH).digest


def test_invalid_brand_is_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    tokens = json.loads(Path(BRAND_PATH).read_text())
    tokens["color"]["accent"] = "not-a-colour"
    bad.write_text(json.dumps(tokens))
    with pytest.raises(BrandError, match="accent"):
        load_brand(bad)


def test_missing_brand_file_is_rejected(tmp_path):
    with pytest.raises(BrandError, match="not found"):
        load_brand(tmp_path / "absent.json")


# --- formats --------------------------------------------------------------


def test_vertical_format_authors_at_4k_and_delivers_at_1080():
    fmt = get_format("9:16")
    assert fmt.authoring == (2160, 3840)
    assert fmt.delivery == (1080, 1920)


def test_safe_area_insets_reserve_platform_chrome():
    top, right, bottom, left = get_format("9:16").safe.inset_px(1080, 1920)
    assert (top, bottom) == (230, 384)  # 12% / 20% of height
    assert right == left == 65


def test_unknown_aspect_is_rejected():
    with pytest.raises(KeyError, match="unknown aspect"):
        get_format("4:3")


# --- slug -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("hydration", "hydration"), ("Vitamin  D!", "vitamin-d"), ("  Sleep & Rest ", "sleep-rest")],
)
def test_slugify(raw, expected):
    assert slugify(raw) == expected


def test_slugify_rejects_unusable_topic():
    with pytest.raises(ValueError):
        slugify("!!!")


# --- end to end -----------------------------------------------------------


def run_cli(tmp_path, *extra):
    """CLI runs stay offline: these cover wiring, not retrieval.

    Live sources are exercised against fakes in test_nodes.py, so the suite
    never depends on Wikipedia or PubMed being reachable.
    """
    return main(
        [
            "--topic", "hydration",
            "--brand", BRAND_PATH,
            "--cache", str(tmp_path / "cache"),
            "--out", str(tmp_path / "out"),
            "--offline",
            *extra,
        ]
    )


def test_cli_emits_a_valid_spec(tmp_path):
    assert run_cli(tmp_path) == 0

    spec = spec_mod.read(tmp_path / "out" / "hydration" / "scene-spec.json")
    spec_mod.validate(spec)
    assert [s["id"] for s in spec["scenes"]] == ["hook", "cta"]
    assert spec["meta"]["resolution"] == [2160, 3840]
    assert spec["audio"]["vo"]["node"] == "voice"
    assert spec["audio"]["words"]


def test_offline_runs_cannot_publish(tmp_path):
    """With no retrieval there is nothing sourced, so the gate stays shut."""
    run_cli(tmp_path)
    spec = spec_mod.read(tmp_path / "out" / "hydration" / "scene-spec.json")
    assert spec["citations"] == []
    assert spec["compliance"]["gate"] == "pending"


def test_provenance_marks_estimated_timings_as_estimated(tmp_path):
    """An estimate must never read as a measurement."""
    run_cli(tmp_path)
    spec = spec_mod.read(tmp_path / "out" / "hydration" / "scene-spec.json")
    provenance = spec["audio"]["provenance"]
    assert provenance["voice"]["backend"] == "null"
    assert provenance["alignment"]["method"] == "estimated"
    assert provenance["beats"] == {"method": "fixed-tempo", "bpm": 92}


def test_uninstalled_backend_exits_with_a_usage_error(tmp_path):
    assert run_cli(tmp_path, "--voice", "kokoro") == 2


def test_spec_is_deterministic_across_runs(tmp_path):
    run_cli(tmp_path)
    first = (tmp_path / "out" / "hydration" / "scene-spec.json").read_text()

    run_cli(tmp_path, "--force", "research")
    assert (tmp_path / "out" / "hydration" / "scene-spec.json").read_text() == first


def test_run_report_records_cache_state_and_provenance(tmp_path):
    run_cli(tmp_path)
    run_cli(tmp_path)

    report = json.loads((tmp_path / "out" / "hydration" / "run.json").read_text())
    assert report["cache"]["hits"] == [
        "research", "script", "voice", "align", "beats", "compose",
    ]
    assert report["brand"]["id"] == "health-v2"
    assert report["backends"]["voice"] == "null"
    assert "generated_utc" in report


def test_generated_spec_carries_no_build_timestamp(tmp_path):
    """A timestamp inside the spec would change its digest every run."""
    run_cli(tmp_path)
    raw = (tmp_path / "out" / "hydration" / "scene-spec.json").read_text()
    assert "generated_utc" not in raw and "created_utc" not in raw


def test_strict_mode_fails_while_warnings_remain(tmp_path):
    assert run_cli(tmp_path, "--strict") == 1


def test_bad_brand_path_exits_with_usage_error(tmp_path):
    assert main(["--topic", "x", "--brand", str(tmp_path / "nope.json")]) == 2


def test_each_aspect_produces_a_valid_spec(tmp_path):
    for aspect in ("9:16", "1:1", "16:9"):
        assert run_cli(tmp_path, "--aspect", aspect) == 0
        spec = spec_mod.read(tmp_path / "out" / "hydration" / "scene-spec.json")
        spec_mod.validate(spec)
        assert spec["meta"]["aspect"] == aspect


def test_spec_carries_safe_area_numbers_not_just_a_name(tmp_path):
    """The motion layer must not need a platform table to place text."""
    run_cli(tmp_path)
    spec = spec_mod.read(tmp_path / "out" / "hydration" / "scene-spec.json")

    assert spec["meta"]["safe_area"] == {
        "name": "social-9x16", "top": 0.12, "right": 0.06, "bottom": 0.2, "left": 0.06,
    }


def test_safe_area_matches_the_aspect(tmp_path):
    run_cli(tmp_path, "--aspect", "16:9")
    spec = spec_mod.read(tmp_path / "out" / "hydration" / "scene-spec.json")
    assert spec["meta"]["safe_area"]["name"] == "social-16x9"
