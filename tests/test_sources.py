from __future__ import annotations

import pytest

from videobot import http
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

        def fetch(self, topic, limit):
            raise RuntimeError("upstream is down")

    class Working:
        kind = "working"

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
