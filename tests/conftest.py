from __future__ import annotations

import copy
from typing import Any

import pytest

_MINIMAL: dict[str, Any] = {
    "version": "1.0",
    "meta": {
        "topic": "hydration",
        "slug": "hydration",
        "duration_s": 4.0,
        "aspect": "9:16",
        "fps": 30,
        "resolution": [2160, 3840],
        "safe_area": {"name": "social-9x16", "top": 0.12, "right": 0.06, "bottom": 0.2, "left": 0.06},
    },
    "brand": {"id": "health-v2", "digest": "abcdef1234567890"},
    "audio": {
        "vo": None,
        "music": None,
        "beats": [],
        "words": [],
        "provenance": {
            "voice": {"backend": "null", "model": "silence"},
            "alignment": {"method": "estimated"},
            "beats": {"method": "fixed-tempo", "bpm": 92},
        },
    },
    "scenes": [
        {
            "id": "hook",
            "in": 0.0,
            "out": 4.0,
            "tier": "A",
            "layout": "statement-center",
            "bg": {"type": "solid"},
            "elements": [
                {
                    "type": "text",
                    "id": "lead",
                    "role": "display",
                    "content": "You are mostly water.",
                    "in": {"at": 0.35, "anim": "rise-blur", "ease": "expo.out", "dur": 0.4},
                    "out": {"at": 3.4, "anim": "fade-scale", "ease": "cubic.in", "dur": 0.22},
                }
            ],
        }
    ],
    "captions": {"style": "karaoke-pop", "max_words": 3, "safe_area": "social-9x16"},
    "citations": [],
    "compliance": {"gate": "pending", "requires_human_signoff": True},
}


@pytest.fixture
def spec() -> dict[str, Any]:
    """A minimal spec that passes every check, for tests to break deliberately."""
    return copy.deepcopy(_MINIMAL)
