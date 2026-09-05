from __future__ import annotations

import pytest

from videobot import http
from videobot.http import FetchError
from videobot.safety import is_citable, screen
from videobot.sources.base import Evidence, SourceSet
from videobot.sources.pubmed import PubMedSource, _identity
from videobot.sources.wikipedia import WikipediaSource, split_sentences

WIKI_PAYLOAD = {
    "title": "Dehydration",
    "revision": "1372280572",
    "extract": (
        "In physiology, dehydration is a lack of total body water. "
        "It occurs when free water loss exceeds intake from excessive sweating. "
        "Short one."
    ),
    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Dehydration"}},
}

PUBMED_SEARCH = {"esearchresult": {"idlist": ["111", "222"]}}
PUBMED_SUMMARY = {
    "result": {
        "uids": ["111", "222"],
        "111": {"title": "Hydration status and cognitive performance in adults.", "source": "J Nutr", "pubdate": "2021 Mar"},
        "222": {"title": "Too short.", "source": "J Nutr", "pubdate": "2020"},
    }
}


def test_split_sentences_drops_fragments():
    assert split_sentences(WIKI_PAYLOAD["extract"]) == [
        "In physiology, dehydration is a lack of total body water.",
        "It occurs when free water loss exceeds intake from excessive sweating.",
    ]


def test_wikipedia_pins_the_revision(monkeypatch):
    monkeypatch.setattr("videobot.sources.wikipedia.get_json", lambda url, params=None: WIKI_PAYLOAD)
    evidence = WikipediaSource().fetch("dehydration", 5)

    assert all(e.source_id == "wikipedia:Dehydration@1372280572" for e in evidence)
    assert all("oldid=1372280572" in e.url for e in evidence)
    assert all(is_citable(e.source_id) for e in evidence)


DISAMBIGUATION = {"type": "disambiguation", "title": "Hydration", "revision": "9", "extract": "Hydration may refer to:Hydrate, a substance that contains water Dough hydration, the percentage of water in a dough in relation to the amount of flour"}

BODY_WATER = {
    "type": "standard",
    "title": "Body water",
    "revision": "1300000001",
    "extract": (
        "In physiology, body water is the water content of an animal body. "
        "The percentages contained in various fluid compartments add up to total body water."
    ),
    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Body_water"}},
}


def _routed(pages, summaries):
    """Fake get_json that answers search and summary calls from fixtures."""

    def get_json(url, params=None):
        if url.startswith("https://en.wikipedia.org/w/rest.php"):
            return {"pages": pages}
        key = url.rsplit("/", 1)[-1]
        return summaries[key]

    return get_json


def test_a_disambiguation_page_never_becomes_evidence(monkeypatch):
    """The bread-dough bug: every sense of a word, each one citable.

    "Hydration may refer to: … Dough hydration, the percentage of water in a
    dough" sentence-splits into claims that trace to a real revision and are
    about the wrong subject entirely.
    """
    monkeypatch.setattr(
        "videobot.sources.wikipedia.get_json",
        _routed(
            [{"key": "Body_water"}],
            {"hydration": DISAMBIGUATION, "Body_water": BODY_WATER},
        ),
    )
    evidence = WikipediaSource().fetch("hydration", 5)

    assert [e.title for e in evidence] == ["Body water", "Body water"]
    assert not any("dough" in e.text.lower() for e in evidence)
    assert all(e.source_id == "wikipedia:Body water@1300000001" for e in evidence)


def test_resolution_skips_a_candidate_that_is_itself_ambiguous(monkeypatch):
    monkeypatch.setattr(
        "videobot.sources.wikipedia.get_json",
        _routed(
            [{"key": "CHI"}, {"key": "Body_water"}],
            {"hydration": DISAMBIGUATION, "CHI": DISAMBIGUATION, "Body_water": BODY_WATER},
        ),
    )
    assert WikipediaSource().fetch("hydration", 5)[0].title == "Body water"


def test_an_article_named_for_the_topic_outranks_search_order(monkeypatch):
    """Search puts Human_body_temperature above Sleep for "sleep human body health"."""
    sleep = dict(BODY_WATER, title="Sleep")
    monkeypatch.setattr(
        "videobot.sources.wikipedia.get_json",
        _routed(
            [{"key": "Human_body_temperature"}, {"key": "Sleep"}],
            {"sleep": DISAMBIGUATION, "Sleep": sleep, "Human_body_temperature": BODY_WATER},
        ),
    )
    assert WikipediaSource().fetch("sleep", 5)[0].title == "Sleep"


def test_an_unresolvable_topic_is_recorded_not_swallowed(monkeypatch):
    """Invariant 7 — a degraded run must be visible, so this raises for gather."""
    monkeypatch.setattr(
        "videobot.sources.wikipedia.get_json",
        _routed([], {"hydration": DISAMBIGUATION}),
    )
    with pytest.raises(FetchError, match="disambiguation"):
        WikipediaSource().fetch("hydration", 5)

    failures = SourceSet((WikipediaSource(),)).gather("hydration", 5).failures
    assert failures and "disambiguation" in failures[0]["error"]


def test_wikipedia_without_a_revision_yields_nothing(monkeypatch):
    """An unpinnable page cannot be cited, so it must not become a claim."""
    monkeypatch.setattr(
        "videobot.sources.wikipedia.get_json", lambda url, params=None: {"extract": "Text.", "title": "X"}
    )
    assert WikipediaSource().fetch("x", 5) == []


def test_pubmed_returns_pmids_and_skips_short_titles(monkeypatch):
    def fake_get_json(url, params=None):
        return PUBMED_SEARCH if "esearch" in url else PUBMED_SUMMARY

    monkeypatch.setattr("videobot.sources.pubmed.get_json", fake_get_json)
    evidence = PubMedSource().fetch("hydration", 2)

    assert [e.source_id for e in evidence] == ["PMID:111"]
    assert evidence[0].url == "https://pubmed.ncbi.nlm.nih.gov/111/"
    assert evidence[0].title == "J Nutr 2021"


def test_pubmed_with_no_hits(monkeypatch):
    monkeypatch.setattr(
        "videobot.sources.pubmed.get_json",
        lambda url, params=None: {"esearchresult": {"idlist": []}},
    )
    assert PubMedSource().fetch("zzz", 3) == []


def test_ncbi_identity_omits_email_unless_opted_in(monkeypatch):
    """A contact address is the operator's to volunteer, not ours to send."""
    monkeypatch.delenv("NCBI_EMAIL", raising=False)
    assert "email" not in _identity()

    monkeypatch.setenv("NCBI_EMAIL", "me@example.com")
    assert _identity()["email"] == "me@example.com"


def test_a_failing_source_does_not_stop_the_run():
    class Broken:
        kind = "broken"
        version = "1"

        def fetch(self, topic, limit):
            raise RuntimeError("upstream is down")

    class Working:
        kind = "working"
        version = "1"

        def fetch(self, topic, limit):
            return [Evidence("Some fact about water.", "PMID:1", "working", "T", "u")]

    gathered = SourceSet((Broken(), Working())).gather("x", 3)
    assert [e.source_id for e in gathered.evidence] == ["PMID:1"]

    # ...but the failure is recorded, never swallowed: a transient outage that
    # costs the only source of on-screen prose must be visible in the output.
    assert gathered.failures == [{"source": "broken", "error": "RuntimeError: upstream is down"}]


def test_http_client_sends_a_descriptive_agent():
    assert "videobot" in http.USER_AGENT and "http" in http.USER_AGENT


# --- safety ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Take 500 mg twice daily.", "dosage"),
        ("Adjust the dosage carefully.", "dosage"),
        ("This herb cures insomnia.", "treatment"),
        ("A new treatment for migraine", "treatment"),
        ("Your doctor will diagnose the cause.", "diagnosis"),
        ("It interacts with blood thinners.", "interaction"),
        ("Furosemide-induced dehydration in rabbits", "named_drug"),
        ("This supplement prevents kidney stones.", "supplement_claim"),
    ],
)
def test_blocked_categories(text, category):
    verdict = screen(text)
    assert not verdict.allowed
    assert verdict.category == category
    assert verdict.reason


@pytest.mark.parametrize(
    "text",
    [
        "In physiology, dehydration is a lack of total body water.",
        "It occurs when free water loss exceeds intake, often from sweating.",
        "Roughly 60% of the adult human body is water.",
    ],
)
def test_ordinary_sourced_statements_pass(text):
    assert screen(text).allowed


@pytest.mark.parametrize(
    ("source_id", "citable"),
    [
        ("PMID:31910392", True),
        ("wikipedia:Dehydration@1372280572", True),
        ("https://example.com", False),
        ("wikipedia:Dehydration", False),
        ("PMID:", False),
    ],
)
def test_is_citable(source_id, citable):
    assert is_citable(source_id) is citable
