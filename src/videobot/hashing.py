"""Canonical hashing.

Every cache key in the pipeline bottoms out here. The rules are strict on
purpose: if two runs with identical inputs can produce different digests, the
cache silently stops working and every render costs full price.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

DIGEST_LEN = 16
"""Truncated hex length used for on-disk names. 64 bits of sha256 is ample for
a single-machine cache and keeps paths readable."""


def canonical_json(value: Any) -> str:
    """Serialise `value` so that equal data always yields an equal string.

    Raises TypeError on anything not JSON-representable rather than falling
    back to `repr`, which would fold distinct objects onto one key.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest_data(value: Any) -> str:
    """Digest of any JSON-representable value."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()[:DIGEST_LEN]


def digest_bytes(payload: bytes) -> str:
    """Digest of raw artifact content."""
    return hashlib.sha256(payload).hexdigest()[:DIGEST_LEN]
