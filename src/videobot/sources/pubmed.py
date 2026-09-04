"""PubMed source via NCBI E-utilities.

Titles of peer-reviewed articles only — abstracts are not fetched, because a
sentence lifted out of an abstract loses the qualifications that made it true.
A title plus its PMID is a citation the viewer can actually follow.
"""

from __future__ import annotations

import os
from typing import Sequence

from ..http import get_json
from .base import Evidence

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
TOOL = "videobot"


def _identity() -> dict[str, str]:
    """NCBI asks callers to identify themselves.

    The email is opt-in through NCBI_EMAIL: a contact address is the operator's
    to volunteer, not something to send on their behalf.
    """
    identity = {"tool": TOOL}
    email = os.environ.get("NCBI_EMAIL", "").strip()
    if email:
        identity["email"] = email
    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    if api_key:
        identity["api_key"] = api_key
    return identity


class PubMedSource:
    kind = "pubmed"

    def fetch(self, topic: str, limit: int) -> Sequence[Evidence]:
        search = get_json(
            ESEARCH,
            {
                "db": "pubmed",
                "term": topic,
                "retmax": str(limit),
                "retmode": "json",
                "sort": "relevance",
                **_identity(),
            },
        )
        pmids = search.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        summary = get_json(
            ESUMMARY,
            {"db": "pubmed", "id": ",".join(pmids), "retmode": "json", **_identity()},
        )
        results = summary.get("result", {})

        evidence: list[Evidence] = []
        for pmid in results.get("uids", []):
            record = results.get(pmid, {})
            title = (record.get("title") or "").strip().rstrip(".")
            if len(title.split()) < 5:
                continue
            journal = record.get("source") or "PubMed"
            year = (record.get("pubdate") or "").split(" ")[0]
            evidence.append(
                Evidence(
                    text=title,
                    source_id=f"PMID:{pmid}",
                    source_kind=self.kind,
                    title=f"{journal} {year}".strip(),
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                )
            )
        return evidence
