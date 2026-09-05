"""Wikipedia REST source.

Cites a pinned revision id, so a claim can always be traced to the exact text
that supported it even after the article changes.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, Sequence

from ..http import FetchError, get_json
from .base import Evidence

SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/page"

DISAMBIGUATION = "disambiguation"
"""The REST summary labels its own page type. A one-field check that nobody
made is how a video about human hydration came to be about bread dough."""

RESOLVE_QUALIFIER = "human body health"
"""Steers an ambiguous term towards the sense this pipeline is about. Measured:
"hydration" alone ranks the chemistry and a drink brand above anything
physiological; "hydration human body health" returns Body_water first."""

MAX_CANDIDATES = 5

_PHYSIOLOGY = re.compile(
    r"\b(physiolog\w*|human\w*|bod(?:y|ies)|health\w*|nutrition\w*|diet\w*|blood|"
    r"cells?|tissues?|muscles?|kidneys?|brain|heart|organs?|metabol\w*|intake|thirst|"
    r"sweat\w*|dehydrat\w*|patients?|clinical|exercise|sleep\w*)\b",
    re.I,
)
_CHEMISTRY = re.compile(
    r"\b(formula|chemical\w*|compounds?|molecul\w*|reagent|synthes\w*|ions?|salts?|"
    r"crystal\w*|solvents?|laborator\w*|diol|precursors?|oxides?|polymer\w*|"
    r"enthalpy|reaction)\b",
    re.I,
)

MIN_DOMAIN_SCORE = 1
"""Below this, nothing on the page says it is about a body.

Search rank alone is not a safe tie-break: the same query returned Body_water
first on one call and Chloral_hydrate — "a geminal diol", a sedative — high
enough to win on another. Picking by rank makes the chosen *article* vary
between runs, which is a far worse failure than a revision moving under a
pinned citation.
"""

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
_WORDS = re.compile(r"\W+")


def split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries, keeping abbreviations intact enough.

    Deliberately simple: the downstream safety filter and human sign-off are
    what protect correctness, not a cleverer splitter.
    """
    parts = [part.strip() for part in _SENTENCE_END.split(text.strip())]
    return [part for part in parts if len(part.split()) >= 5]


def _title_words(text: str) -> set[str]:
    return {word for word in _WORDS.split(text.lower()) if len(word) > 3}


def domain_score(text: str) -> int:
    """How much a page reads as human physiology rather than chemistry.

    Both senses of "hydration" are about water, so water words cannot separate
    them. What separates them is whether the page talks about bodies or about
    formulae.
    """
    return len(_PHYSIOLOGY.findall(text)) - len(_CHEMISTRY.findall(text))


class WikipediaSource:
    kind = "wikipedia"
    version = "2"

    def fetch(self, topic: str, limit: int) -> Sequence[Evidence]:
        payload = self._summary(topic)

        # A disambiguation extract is a list of unrelated senses — "Hydration
        # may refer to: … Dough hydration, the percentage of water in a dough".
        # Sentence-split, each line becomes a citable claim about the wrong
        # subject, correctly attributed to a real revision. Sourced is not the
        # same as relevant, and the compliance gate only checks the first.
        if payload.get("type") == DISAMBIGUATION:
            payload = self._resolve(topic)

        extract = payload.get("extract") or ""
        revision = str(payload.get("revision") or "")
        page_title = payload.get("title") or topic
        if not extract or not revision:
            return []

        title = urllib.parse.quote(page_title.replace(" ", "_"), safe="")
        url = (
            payload.get("content_urls", {}).get("desktop", {}).get("page")
            or f"https://en.wikipedia.org/wiki/{title}"
        )
        return [
            Evidence(
                text=sentence,
                source_id=f"wikipedia:{page_title}@{revision}",
                source_kind=self.kind,
                title=page_title,
                url=f"{url}?oldid={revision}",
            )
            for sentence in split_sentences(extract)[:limit]
        ]

    def _summary(self, title: str) -> dict[str, Any]:
        quoted = urllib.parse.quote(title.strip().replace(" ", "_"), safe="")
        return get_json(SUMMARY_URL.format(title=quoted))

    def _resolve(self, topic: str) -> dict[str, Any]:
        """Pick the article an ambiguous term means in a health context.

        Raises rather than returning nothing: an unresolvable topic is a
        retrieval failure, and failures are recorded in `compliance.notes`
        (invariant 7). Silently returning no evidence would leave the run
        looking merely thin instead of wrong.
        """
        results = get_json(SEARCH_URL, {"q": f"{topic} {RESOLVE_QUALIFIER}", "limit": MAX_CANDIDATES})
        pages = results.get("pages") or []

        # An article whose own title carries the topic word is the better read
        # of it; sorting is stable, so everything else keeps search rank.
        wanted = _title_words(topic)
        ranked = sorted(pages, key=lambda page: 0 if wanted & _title_words(page.get("key") or "") else 1)

        # Rank picks *which* article; the domain score only decides whether a
        # candidate is eligible at all. Scoring the choice instead was worse:
        # it returned Body_fat_percentage for "hydration", because that page
        # says "body" more often than the page actually about body water.
        for page in ranked:
            key = page.get("key")
            if not key:
                continue
            candidate = self._summary(key)
            if candidate.get("type") == DISAMBIGUATION:
                continue
            if not (candidate.get("extract") and candidate.get("revision")):
                continue
            if domain_score(f"{page.get('description') or ''} {candidate['extract']}") < MIN_DOMAIN_SCORE:
                continue
            return candidate

        raise FetchError(
            f"{topic!r} is a disambiguation page on Wikipedia and no article about the "
            "human body resolved from it"
        )
