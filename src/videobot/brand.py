"""Brand token loading.

Tokens are data, not code, so a client brand is a new JSON file rather than a
fork of the pipeline.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from .hashing import digest_data
from .schema_util import load_schema, schema_errors


class BrandError(ValueError):
    """Raised when a token file is missing or fails its schema."""


@dataclass(frozen=True)
class Brand:
    """Validated tokens plus the digest that pins a render to this exact file."""

    tokens: dict[str, Any]

    @property
    def id(self) -> str:
        return self.tokens["id"]

    @cached_property
    def digest(self) -> str:
        return digest_data(self.tokens)

    def ref(self) -> dict[str, str]:
        """The `brand` block embedded in a scene spec."""
        return {"id": self.id, "digest": self.digest}

    # Motion accessors — the values scenes reach for constantly.

    def ease(self, kind: str) -> str:
        return self.tokens["motion"]["ease"][kind]

    def duration_s(self, kind: str) -> float:
        """Token durations are authored in ms; the spec speaks seconds."""
        return self.tokens["motion"]["duration_ms"][kind] / 1000.0

    @property
    def stagger_s(self) -> float:
        return self.tokens["motion"]["stagger_ms"] / 1000.0

    def captions_block(self, safe_area: str) -> dict[str, Any]:
        caps = self.tokens["captions"]
        return {"style": caps["style"], "max_words": caps["max_words"], "safe_area": safe_area}


def load_brand(path: str | Path) -> Brand:
    """Read and validate a token file."""
    path = Path(path)
    if not path.exists():
        raise BrandError(f"brand token file not found: {path}")
    try:
        tokens = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise BrandError(f"{path}: invalid JSON — {exc}") from exc

    # `$schema` is an editor affordance, not part of the token data, and would
    # otherwise leak into the digest and change it when the file moves.
    tokens.pop("$schema", None)

    errors = schema_errors(tokens, load_schema("brand-tokens"))
    if errors:
        joined = "\n  - ".join(errors)
        raise BrandError(f"{path}: token validation failed:\n  - {joined}")
    return Brand(tokens=tokens)
