"""Wikipedia REST source.

Cites a pinned revision id, so a claim can always be traced to the exact text
that supported it even after the article changes.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Sequence

from ..http import get_json
from .base import Evidence

SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


def split_sentences(text: str) -> list[str]:
    """Split on sentence boundaries, keeping abbreviations intact enough.

    Deliberately simple: the downstream safety filter and human sign-off are
    what protect correctness, not a cleverer splitter.
    """
    parts = [part.strip() for part in _SENTENCE_END.split(text.strip())]
    return [part for part in parts if len(part.split()) >= 5]


class WikipediaSource:
    kind = "wikipedia"

    def fetch(self, topic: str, limit: int) -> Sequence[Evidence]:
        title = urllib.parse.quote(topic.strip().replace(" ", "_"), safe="")
        payload = get_json(SUMMARY_URL.format(title=title))

        extract = payload.get("extract") or ""
        revision = str(payload.get("revision") or "")
        page_title = payload.get("title") or topic
        if not extract or not revision:
            return []

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
