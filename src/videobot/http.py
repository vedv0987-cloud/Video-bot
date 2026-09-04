"""Minimal HTTP client for the retrieval sources.

stdlib only: `urllib` already honours HTTPS_PROXY and the system CA bundle,
which is what this environment needs, and a source that fetches two URLs does
not justify a dependency.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = "videobot/0.2 (https://github.com/vedv0987-cloud/Video-bot)"
"""Wikipedia rejects requests without a descriptive agent, and NCBI asks that
callers identify themselves. Being a good citizen here is not optional."""

TIMEOUT_S = 20.0
MIN_INTERVAL_S = 0.35
"""NCBI allows ~3 requests/second unauthenticated. Stay under it."""

_last_request_at = 0.0


class FetchError(RuntimeError):
    """Raised when a source cannot be reached or returns a bad response."""


def get_json(url: str, params: dict[str, Any] | None = None) -> Any:
    """GET a URL and parse JSON, throttled and with a descriptive agent."""
    global _last_request_at

    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - elapsed)

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            payload = response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise FetchError(f"{url}: {exc}") from exc
    finally:
        _last_request_at = time.monotonic()

    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{url}: response was not JSON — {exc}") from exc
