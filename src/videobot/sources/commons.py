"""Wikimedia Commons image source.

Imagery is the difference between a slideshow and a video, and it has the same
provenance problem as the claims: a picture with no licence is not usable, so
every candidate carries its licence and attribution or it is dropped.

Only permissive licences are accepted. Attribution travels with the image all
the way into the spec, so the render can credit it on screen.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Sequence

from ..http import get_json

API = "https://commons.wikimedia.org/w/api.php"

ALLOWED_LICENCES = (
    "cc0",
    "public domain",
    "cc by",
    "cc by-sa",
    "cc-by",
    "cc-by-sa",
)
"""Permissive only. CC BY-SA is included because attribution is recorded and
shown; anything non-commercial or unclear is rejected rather than guessed at."""

MIN_WIDTH = 1200
MIN_ASPECT = 0.55
MAX_ASPECT = 1.9
"""Reject banners and letterbox crops: a 2344x335 strip cannot fill a 9:16
frame, and upscaling it to fit is exactly the cheap look we are avoiding."""

_TAG = re.compile(r"<[^>]+>")

_NON_COMMERCIAL = re.compile(r"\bn[\s-]?c\b|non[\s-]?commercial|\bnd\b|no[\s-]?deriv", re.I)
"""`"nc" in licence.split("-")` does not catch "CC BY-NC 2.0" — the hyphen
split leaves "nc 2.0". Match the token instead. NoDerivs is excluded too: a
still that cannot be cropped or graded is not usable in an edit."""

_CLINICAL = re.compile(
    r"\b(patient|hospital|clinic|surgery|surgical|wound|autopsy|cadaver|"
    r"lesion|infection|disease|corpse|victim|injury|blood)\b",
    re.I,
)
"""Commons is full of medical documentation photographs. They are correctly
licensed and completely wrong for a health short — clinical imagery reads as
alarming, and using a real patient's photograph as decoration is not something
to do by accident."""


def _plain(value: str) -> str:
    """Commons metadata is HTML; the spec wants text."""
    return html.unescape(_TAG.sub("", value or "")).strip()


@dataclass(frozen=True)
class Picture:
    title: str
    url: str
    width: int
    height: int
    licence: str
    artist: str
    page: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "width": self.width,
            "height": self.height,
            "licence": self.licence,
            "artist": self.artist,
            "page": self.page,
        }

    @property
    def credit(self) -> str:
        """One line, as it appears on screen."""
        who = self.artist or "Wikimedia Commons"
        return f"{who} · {self.licence}"


def licence_allowed(licence: str) -> bool:
    lowered = licence.strip().lower()
    if not lowered:
        return False
    if _NON_COMMERCIAL.search(lowered):
        return False
    return any(lowered.startswith(allowed) for allowed in ALLOWED_LICENCES)


def subject_allowed(title: str) -> bool:
    """Whether a file's title suggests imagery fit to put on screen."""
    return not _CLINICAL.search(title)


class CommonsImageSource:
    """Searches Commons for usable stills on a topic."""

    kind = "commons"
    version = "1"

    def fetch(self, topic: str, limit: int) -> Sequence[Picture]:
        payload = get_json(
            API,
            {
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{topic} -logo -diagram -map",
                "gsrnamespace": "6",
                # Over-fetch: licence and shape filters reject most candidates.
                "gsrlimit": str(max(limit * 6, 24)),
                "prop": "imageinfo",
                "iiprop": "url|extmetadata|size",
                "iiurlwidth": "1600",
                "format": "json",
            },
        )

        pages = (payload.get("query") or {}).get("pages") or {}
        pictures: list[Picture] = []

        # `pages` is a dict keyed by page id; search rank lives in `index`.
        for page in sorted(pages.values(), key=lambda p: p.get("index", 0)):
            info = (page.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata") or {}

            licence = _plain(meta.get("LicenseShortName", {}).get("value", ""))
            if not licence_allowed(licence):
                continue

            title = _plain(page.get("title", "")).removeprefix("File:")
            if not subject_allowed(title):
                continue

            width = int(info.get("thumbwidth") or info.get("width") or 0)
            height = int(info.get("thumbheight") or info.get("height") or 0)
            if width < MIN_WIDTH or height <= 0:
                continue
            aspect = width / height
            if not MIN_ASPECT <= aspect <= MAX_ASPECT:
                continue

            url = info.get("thumburl") or info.get("url")
            if not url:
                continue

            pictures.append(
                Picture(
                    title=title,
                    url=url,
                    width=width,
                    height=height,
                    licence=licence,
                    artist=_plain(meta.get("Artist", {}).get("value", ""))[:80],
                    page=info.get("descriptionurl", ""),
                )
            )
            if len(pictures) >= limit:
                break

        return pictures
