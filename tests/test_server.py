from __future__ import annotations

import json

import pytest

from videobot.server import NODE_NAMES, Studio, _choice, _render_flags


@pytest.fixture
def studio(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    return Studio(root=tmp_path, out=out, cache=tmp_path / "cache", brand=tmp_path / "brand.json")


def _write_run(out, slug, *, video=True):
    directory = out / slug
    directory.mkdir()
    (directory / "scene-spec.json").write_text(
        json.dumps(
            {
                "meta": {"topic": slug, "duration_s": 12.5},
                "scenes": [{}, {}],
                "citations": [{}],
                "compliance": {"gate": "passed"},
            }
        )
    )
    if video:
        (directory / f"{slug}-9x16.mp4").write_bytes(b"\x00")
    return directory


# --- the checklist tracks the graph ---------------------------------------


def test_the_step_list_comes_from_the_graph():
    """A hand-written list of stages would drift the moment a node is added."""
    assert NODE_NAMES == ["research", "script", "media", "voice", "align", "beats", "compose"]


# --- input handling -------------------------------------------------------


def test_a_topic_that_cannot_be_a_slug_is_rejected_before_anything_runs(studio):
    with pytest.raises(ValueError):
        studio.start({"topic": "!!!"})
    assert studio.jobs == {}


def test_unknown_options_fall_back_rather_than_reaching_the_pipeline():
    """The browser is not trusted to send a valid backend name."""
    assert _choice("kokoro", {"kokoro", "null"}, "null") == "kokoro"
    assert _choice("evil", {"kokoro", "null"}, "null") == "null"
    assert _choice(None, {"kokoro"}, "null") == "null"
    assert _choice({"$ne": 1}, {"kokoro"}, "null") == "null"


def test_render_flags_are_built_from_constants_not_from_input():
    """Nothing a user types can become an ffmpeg or node argument."""
    assert _render_flags({"preview": True}) == ["--scale", "0.25", "--seconds", "4"]
    assert _render_flags({"preview": "; rm -rf /"}) == ["--scale", "0.25", "--seconds", "4"]
    assert _render_flags({}) == []


# --- serving files --------------------------------------------------------


def test_media_outside_the_output_tree_is_refused(studio, tmp_path):
    """Path traversal: resolve first, then check containment."""
    secret = tmp_path / "secret.txt"
    secret.write_text("private")

    with pytest.raises(FileNotFoundError):
        studio.media("../secret.txt")
    with pytest.raises(FileNotFoundError):
        studio.media("../../etc/passwd")


def test_a_symlink_pointing_out_of_the_tree_is_refused(studio, tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("private")
    (studio.out / "escape.mp4").symlink_to(secret)

    with pytest.raises(FileNotFoundError):
        studio.media("escape.mp4")


def test_media_inside_the_tree_resolves(studio):
    _write_run(studio.out, "hydration")
    assert studio.media("hydration/hydration-9x16.mp4").name == "hydration-9x16.mp4"


# --- the library ----------------------------------------------------------


def test_the_library_summarises_finished_runs(studio):
    _write_run(studio.out, "hydration")
    runs = studio.runs()

    assert runs[0]["topic"] == "hydration"
    assert runs[0]["scenes"] == 2
    assert runs[0]["gate"] == "passed"
    assert runs[0]["video"] == "/media/hydration/hydration-9x16.mp4"


def test_a_spec_without_a_render_is_still_listed(studio):
    _write_run(studio.out, "sleep", video=False)
    assert studio.runs()[0]["video"] is None


def test_a_directory_without_a_spec_is_skipped(studio):
    (studio.out / "junk").mkdir()
    assert studio.runs() == []


def test_unreadable_spec_does_not_break_the_library(studio):
    """One corrupt run must not take the whole dashboard down."""
    _write_run(studio.out, "good")
    broken = studio.out / "broken"
    broken.mkdir()
    (broken / "scene-spec.json").write_text("{not json")

    assert [run["slug"] for run in studio.runs()] == ["good"]
