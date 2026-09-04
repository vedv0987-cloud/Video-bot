"""Delivery formats and platform safe areas.

Safe areas are platform facts, not brand choices, so they live here rather than
in the token file. Compose at 4K and deliver down (UPGRADE-PLAN §5.9).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SafeArea:
    """Fractions of the frame that platform chrome can cover.

    On a 9:16 feed the top strip carries the account header and the bottom
    carries caption, handle, and the action rail — so titles and captions live
    in the middle band (UPGRADE-PLAN §5.3).
    """

    name: str
    top: float
    bottom: float
    left: float
    right: float

    def inset_px(self, width: int, height: int) -> tuple[int, int, int, int]:
        """Safe-area inset in pixels as (top, right, bottom, left)."""
        return (
            round(self.top * height),
            round(self.right * width),
            round(self.bottom * height),
            round(self.left * width),
        )


SAFE_AREAS: dict[str, SafeArea] = {
    # Shared worst case across TikTok / Reels / Shorts rather than one per app:
    # a single conservative band means one render is safe everywhere.
    "social-9x16": SafeArea("social-9x16", top=0.12, bottom=0.20, left=0.06, right=0.06),
    "social-1x1": SafeArea("social-1x1", top=0.06, bottom=0.10, left=0.06, right=0.06),
    "social-16x9": SafeArea("social-16x9", top=0.05, bottom=0.08, left=0.05, right=0.05),
}


@dataclass(frozen=True)
class Format:
    """An aspect ratio with its authoring and delivery resolutions."""

    aspect: str
    authoring: tuple[int, int]
    delivery: tuple[int, int]
    safe_area: str
    fps: int = 30

    @property
    def safe(self) -> SafeArea:
        return SAFE_AREAS[self.safe_area]


FORMATS: dict[str, Format] = {
    "9:16": Format("9:16", (2160, 3840), (1080, 1920), "social-9x16"),
    "1:1": Format("1:1", (2160, 2160), (1080, 1080), "social-1x1"),
    "16:9": Format("16:9", (3840, 2160), (1920, 1080), "social-16x9"),
}


def get_format(aspect: str) -> Format:
    try:
        return FORMATS[aspect]
    except KeyError:
        raise KeyError(f"unknown aspect {aspect!r}; expected one of {', '.join(FORMATS)}") from None
