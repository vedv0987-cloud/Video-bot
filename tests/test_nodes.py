from __future__ import annotations

import pytest

from videobot import spec as spec_mod
from videobot.brand import load_brand
from videobot.cache import Cache
from videobot.dag import Runner
from videobot.nodes import default_nodes
from videobot.nodes.compose import MIN_SCENE_S, scene_boundaries
from videobot.nodes.script import (
    InventedClaimError,
    TemplateRewriter,
    assert_no_invented_claims,
)
from videobot.sources.base import Evidence, SourceSet
from conftest import BRAND_PATH

CLAIMS = [
    {"id": "c1", "text": "About 60% of the adult body is water.", "display": True},
    {"id": "c2", "text": "Water regulates body temperature.", "display": True},
]


# --- the rewriter invariant ----------------------------------------------


def test_quoting_a_source_is_allowed():
    assert_no_invented_claims(
        CLAIMS, [{"id": "s", "text": "About 60% of the adult body is water.", "cites": ["c1"]}]
    )


def test_citing_an_unknown_claim_is_rejected():
    with pytest.raises(InventedClaimError, match="unknown claim"):
        assert_no_invented_claims(CLAIMS, [{"id": "s", "text": "Anything.", "cites": ["c9"]}])


def test_inventing_a_statistic_is_rejected():
    """The check that matters: models invent plausible numbers readily."""
    with pytest.raises(InventedClaimError, match="states '75'"):
        assert_no_invented_claims(
            CLAIMS, [{"id": "s", "text": "About 75% of the body is water.", "cites": ["c1"]}]
        )


def test_a_number_must_come_from_the_cited_claim_not_a_sibling():
    with pytest.raises(InventedClaimError):
        assert_no_invented_claims(
            CLAIMS, [{"id": "s", "text": "About 60% of it.", "cites": ["c2"]}]
        )


def test_numbers_inside_list_items_are_checked_too():
    with pytest.raises(InventedClaimError, match="states '99'"):
        assert_no_invented_claims(
            CLAIMS, [{"id": "s", "text": "Facts:", "items": ["99% water"], "cites": ["c1"]}]
        )


def test_connective_text_stays_digit_free():
    """A reference tally is bookkeeping, not something a source said."""
    sections = TemplateRewriter().sections("hydration", CLAIMS)
    for section in sections:
        if section["kind"] in {"hook", "cta"}:
            assert not any(char.isdigit() for char in section["text"])


def test_rewriter_caps_the_number_of_cards():
    many = [dict(c, id=f"c{i}") for i, c in enumerate([CLAIMS[0]] * 8)]
    sections = TemplateRewriter().sections("x", many)
    assert sum(1 for s in sections if s["kind"] == "point") == 3


# --- scene boundaries -----------------------------------------------------

BEATS = [round(i * 0.5, 3) for i in range(40)]


def sections(*spans):
    return [{"id": f"s{i}", "t0": a, "t1": b} for i, (a, b) in enumerate(spans)]


def test_boundaries_start_at_zero_and_end_at_the_duration():
    bounds = scene_boundaries(sections((0, 3), (3.2, 8)), 8.5, BEATS)
    assert bounds[0] == 0.0
    assert bounds[-1] == 8.5


def test_a_cut_snaps_to_a_nearby_beat():
    """Midpoint 3.1 is within 120ms of the 3.0 beat."""
    assert scene_boundaries(sections((0, 3.0), (3.2, 8)), 8.5, BEATS)[1] == 3.0


def test_a_cut_far_from_a_beat_is_left_alone():
    bounds = scene_boundaries(sections((0, 3.2), (3.3, 8)), 8.5, BEATS)
    assert bounds[1] == pytest.approx(3.25)


def test_boundaries_never_produce_an_unreadable_scene():
    bounds = scene_boundaries(sections((0, 0.4), (0.5, 0.9), (1.0, 6)), 7.0, BEATS)
    assert all(b - a >= MIN_SCENE_S - 1e-6 for a, b in zip(bounds, bounds[1:])), bounds


def test_boundaries_are_strictly_increasing():
    bounds = scene_boundaries(sections((0, 2), (2.1, 4), (4.1, 9)), 9.5, BEATS)
    assert bounds == sorted(bounds)


# --- the whole graph ------------------------------------------------------


class FakeSource:
    kind = "wikipedia"

    def __init__(self, *evidence: Evidence) -> None:
        self._evidence = evidence

    def fetch(self, topic, limit):
        return self._evidence[:limit]


def wiki(text: str) -> Evidence:
    return Evidence(text, "wikipedia:Test@42", "wikipedia", "Test", "https://example.org?oldid=42")


def run_graph(tmp_path, sources, **overrides):
    ctx = {
        "topic": "hydration",
        "slug": "hydration",
        "aspect": "9:16",
        "brand": load_brand(BRAND_PATH),
        "sources": sources,
        "rewriter": "template",
        "voice": "null",
        "aligner": "estimated",
        "beats": "fixed-tempo",
        "bpm": 92,
        # Retrieval of imagery is exercised separately; graph tests stay offline.
        "media": False,
        "cache_root": tmp_path / "cache",
        **overrides,
    }
    report = Runner(Cache(tmp_path / "cache"), default_nodes()).run(ctx)
    return report.artifacts["compose"].read_json()


def test_graph_produces_a_valid_cited_spec(tmp_path):
    spec = run_graph(
        tmp_path,
        SourceSet(
            (
                FakeSource(
                    wiki("Water makes up most of the adult human body by mass."),
                    wiki("It moves nutrients through the bloodstream to every tissue."),
                ),
            )
        ),
    )
    spec_mod.validate(spec)

    assert spec["compliance"]["gate"] == "passed"
    assert len(spec["citations"]) == 2
    assert all(c["source"] == "wikipedia:Test@42" for c in spec["citations"])
    assert spec["audio"]["provenance"]["voice"]["backend"] == "null"


def test_a_screened_passage_never_reaches_the_spec(tmp_path):
    spec = run_graph(
        tmp_path,
        SourceSet(
            (
                FakeSource(
                    wiki("Water makes up most of the adult human body by mass."),
                    wiki("Doctors prescribe furosemide for fluid retention in patients."),
                ),
            )
        ),
    )
    spec_mod.validate(spec)

    on_screen = " ".join(e["content"] for s in spec["scenes"] for e in s["elements"])
    assert "furosemide" not in on_screen.lower()
    assert not any("furosemide" in c["claim"].lower() for c in spec["citations"])
    assert any("safety screen" in note for note in spec["compliance"]["notes"])


def test_no_sources_cannot_pass_the_gate(tmp_path):
    spec = run_graph(tmp_path, SourceSet(()))
    spec_mod.validate(spec)

    assert spec["citations"] == []
    assert spec["compliance"]["gate"] == "pending"
    assert any("nothing on screen is sourced" in note for note in spec["compliance"]["notes"])


def test_every_claim_card_carries_a_citation(tmp_path):
    spec = run_graph(
        tmp_path,
        SourceSet((FakeSource(wiki("Water makes up most of the adult human body by mass.")),)),
    )
    cited = {c["id"] for c in spec["citations"]}
    for scene in spec["scenes"]:
        if scene["layout"] == "statement-card":
            assert scene["elements"][0]["cite"] in cited


def test_scene_count_follows_the_retrieved_evidence(tmp_path):
    spec = run_graph(
        tmp_path,
        SourceSet(
            (
                FakeSource(
                    wiki("Water makes up most of the adult human body by mass."),
                    wiki("It moves nutrients through the bloodstream to every tissue."),
                    wiki("Thirst is a late signal of fluid loss in most adults."),
                    wiki("Fluid needs vary with climate and activity across people."),
                ),
            )
        ),
    )
    # hook + 3 capped cards + cta
    assert len(spec["scenes"]) == 5


class BrokenSource:
    kind = "wikipedia"

    def fetch(self, topic, limit):
        raise RuntimeError("upstream is down")


def test_a_source_outage_is_reported_and_blocks_the_gate(tmp_path):
    """Losing the only prose source must not yield a healthy-looking empty cut."""
    spec = run_graph(tmp_path, SourceSet((BrokenSource(),)))
    spec_mod.validate(spec)

    assert spec["compliance"]["gate"] == "pending"
    assert any("source wikipedia failed" in note for note in spec["compliance"]["notes"])
    assert any("upstream is down" in note for note in spec["compliance"]["notes"])


def test_references_without_claim_cards_cannot_pass_the_gate(tmp_path):
    """Citations the viewer never sees are not sourced content."""

    class RefsOnly:
        kind = "pubmed"

        def fetch(self, topic, limit):
            return [Evidence("A study of fluid balance in adults.", "PMID:7", "pubmed", "J", "u")]

    spec = run_graph(tmp_path, SourceSet((RefsOnly(),)))
    spec_mod.validate(spec)

    assert spec["citations"]
    assert spec["compliance"]["gate"] == "pending"
    assert any("no claim cards" in note for note in spec["compliance"]["notes"])
    assert any("no claim cards" in w for w in spec_mod.lint(spec))
