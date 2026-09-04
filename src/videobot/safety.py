"""Health-content screening (UPGRADE-PLAN §7.1).

Two separate ideas, kept separate on purpose:

*Verified* means a claim is quoted from a retrievable, pinned source — a PMID
or a Wikipedia revision. It does not mean a clinician has endorsed it, which is
why `requires_human_signoff` stays true no matter how clean this comes back.

*Screened* means the claim avoids the categories that a 40-second video is the
wrong medium for at any level of sourcing. The patterns below deliberately
over-block: a dropped claim costs one sentence, a published dosage costs
rather more. Every drop is reported with its reason, so nothing disappears
silently.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    category: str = ""
    reason: str = ""


# (category, pattern, why it is blocked)
RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "dosage",
        re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|µg|kg|ml|iu|units?)\b", re.I),
        "states a quantity that reads as a dose",
    ),
    (
        "dosage",
        re.compile(r"\b(?:dosage|dosing|dose[sd]?|administer(?:ed|ing)?|inject(?:ed|ion))\b", re.I),
        "describes administering a substance",
    ),
    (
        "treatment",
        re.compile(
            r"\b(?:cure[sd]?|curing|treat(?:s|ed|ing|ment|ments)?|"
            r"remed(?:y|ies)|therap(?:y|ies|eutic)|heal(?:s|ed|ing))\b",
            re.I,
        ),
        "frames the topic as treating or curing a condition",
    ),
    (
        "diagnosis",
        re.compile(r"\b(?:diagnos(?:e|es|ed|is|tic)|prognosis|you (?:probably )?have)\b", re.I),
        "reads as diagnosing the viewer",
    ),
    (
        "interaction",
        re.compile(r"\b(?:interacts? with|contraindicat\w*|drug[- ]drug|side[- ]effects?)\b", re.I),
        "describes drug interactions or side effects",
    ),
    (
        "named_drug",
        re.compile(
            r"\b\w{3,}(?:cillin|mycin|prazole|statin|sartan|olol|semide|azepam|"
            r"codone|profen|caine|tinib|mab)\b",
            re.I,
        ),
        "names a specific pharmaceutical",
    ),
    (
        "supplement_claim",
        re.compile(r"\bsupplements?\b.{0,40}\b(?:prevent|reverse|boost|fix|protect)\w*\b", re.I),
        "makes a therapeutic claim for a supplement",
    ),
)


def screen(text: str) -> Verdict:
    """Screen one passage against every blocked category."""
    for category, pattern, reason in RULES:
        match = pattern.search(text)
        if match:
            return Verdict(False, category, f"{reason} ({match.group(0)!r})")
    return Verdict(True)


def is_citable(source_id: str) -> bool:
    """Whether a source id is specific enough to trace.

    A bare domain is not a citation; a PMID or a pinned revision is.
    """
    return bool(re.fullmatch(r"PMID:\d+", source_id) or re.match(r"wikipedia:.+@\d+$", source_id))
