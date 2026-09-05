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

USER_AGENT = "videobot/0.3 (https://github.com/vedv0987-cloud/Video-bot)"
"""Wikipedia rejects requests without a descriptive agent, and NCBI asks that
callers identify themselves. Being a good citizen here is not optional."""

TIMEOUT_S = 20.0
MIN_INTERVAL_S = 0.35
"""NCBI allows ~3 requests/second unauthenticated. Stay under it."""

RETRY_STATUS = {429, 503}
MAX_ATTEMPTS = 4
"""A rate limit is a "come back later", not a failure. Wikimedia in particular
will 429 a burst that a second of patience would have served."""

_last_request_at = 0.0


class FetchError(RuntimeError):
    """Raised when a source cannot be reached or returns a bad response."""


def get_bytes(url: str, headers: dict[str, str] | None = None) -> bytes:
    """GET raw bytes — images, video, anything not JSON."""
    return _fetch(url, headers)


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    """GET a URL and parse JSON, throttled and with a descriptive agent.

    `headers` carries API keys. They belong in a header rather than a query
    string: a URL ends up in logs, in exception messages and in `run.json`,
    and a key that leaks there has leaked everywhere.
    """
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    payload = _fetch(url, headers)
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FetchError(f"{url}: response was not JSON — {exc}") from exc


def _fetch(url: str, headers: dict[str, str] | None = None) -> bytes:
    """One throttled, retrying GET."""
    global _last_request_at

    elapsed = time.monotonic() - _last_request_at
    if elapsed < MIN_INTERVAL_S:
        time.sleep(MIN_INTERVAL_S - elapsed)

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})

    payload: bytes | None = None
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                payload = response.read()
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in RETRY_STATUS or attempt == MAX_ATTEMPTS - 1:
                break
            # Honour Retry-After when the server sends one; otherwise back off.
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = float(retry_after) if (retry_after or "").isdigit() else 2.0 * (2**attempt)
            time.sleep(min(delay, 30.0))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            break
        finally:
            _last_request_at = time.monotonic()

    if payload is None:
        raise FetchError(f"{url}: {last_error}") from last_error
    return payload
