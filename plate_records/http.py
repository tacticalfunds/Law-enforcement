"""Tiny HTTP helper built on the standard library.

Uses urllib so the package has zero third-party dependencies. Honors the
standard HTTPS_PROXY / REQUESTS_CA_BUNDLE style environment so it works behind
corporate or sandbox proxies without extra config.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class HTTPError(RuntimeError):
    """Raised when a request fails or returns a non-2xx status."""


def get_json(url: str, params: dict[str, Any] | None = None, timeout: float = 20.0) -> Any:
    """GET a URL and parse the response as JSON.

    Raises HTTPError on network failure, non-2xx status, or invalid JSON.
    """
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{url}?{query}"

    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "plate-records/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:  # server responded with 4xx/5xx
        raise HTTPError(f"{url} -> HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:  # network / DNS / TLS / proxy failure
        raise HTTPError(f"{url} -> {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPError(f"{url} -> invalid JSON response") from exc
