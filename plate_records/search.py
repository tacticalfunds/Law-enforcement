"""General web search + page-review utilities.

Two capabilities:

  * SearchProvider  -- query a real search API (you supply the key) and get
    back structured results (title, url, snippet).
  * fetch_readable  -- retrieve a URL and extract its readable text, so the
    tool can "review" a page's content instead of just linking to it.

Only a mock search provider ships here. Register a real one (Brave, Bing,
Google Programmable Search, SerpAPI, ...) backed by your own API key.
"""

from __future__ import annotations

import abc
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from .http import HTTPError, get_json  # noqa: F401  (get_json used by real providers)


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


class SearchProvider(abc.ABC):
    name: str = "unnamed-search"

    @abc.abstractmethod
    def search(self, query: str, *, count: int = 10) -> list[SearchResult]:
        """Return up to `count` web results for a free-text query."""


class MockSearchProvider(SearchProvider):
    """Deterministic fake results so the CLI runs without an API key."""

    name = "mock"

    def search(self, query: str, *, count: int = 10) -> list[SearchResult]:
        n = max(1, min(count, 3))
        return [
            SearchResult(
                title=f"Sample result {i} for: {query}",
                url=f"https://example.com/{i}",
                snippet="SAMPLE DATA ONLY - wire in a real search API for live results.",
            )
            for i in range(1, n + 1)
        ]


# ---- Example real provider (kept commented; needs your API key) -------------
#
# class BraveSearchProvider(SearchProvider):
#     name = "brave"
#     def __init__(self, api_key: str):
#         self.api_key = api_key
#     def search(self, query, *, count=10):
#         data = get_json(
#             "https://api.search.brave.com/res/v1/web/search",
#             params={"q": query, "count": count},
#             # NOTE: this helper doesn't send custom headers; a real impl would
#             # add {"X-Subscription-Token": self.api_key}. Left as an exercise
#             # so no half-working key handling ships by default.
#         )
#         return [SearchResult(r["title"], r["url"], r.get("description", ""))
#                 for r in data.get("web", {}).get("results", [])]

SEARCH_PROVIDERS: dict[str, type[SearchProvider]] = {
    "mock": MockSearchProvider,
}


def get_search_provider(name: str) -> SearchProvider:
    try:
        return SEARCH_PROVIDERS[name]()
    except KeyError:
        available = ", ".join(sorted(SEARCH_PROVIDERS)) or "(none)"
        raise SystemExit(f"Unknown search provider {name!r}. Available: {available}")


# ---- Page review (fetch + extract readable text) ----------------------------

class _TextExtractor(HTMLParser):
    """Strip scripts/styles and collect visible text."""

    _SKIP = {"script", "style", "noscript", "head", "template"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title and not self.title:
            self.title = text
        else:
            self._chunks.append(text)

    @property
    def text(self) -> str:
        joined = " ".join(self._chunks)
        return re.sub(r"\s+", " ", joined).strip()


@dataclass
class PageReview:
    url: str
    title: str
    text: str

    def preview(self, limit: int = 2000) -> str:
        return self.text[:limit] + ("..." if len(self.text) > limit else "")


def fetch_readable(url: str, timeout: float = 20.0, max_bytes: int = 2_000_000) -> PageReview:
    """Fetch a URL and return its title + readable text.

    Uses only the standard library. Caps the download size so a huge page
    can't blow up memory. Raises HTTPError on failure.
    """
    import urllib.error
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "plate-records/0.1 (+research)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(max_bytes)
            charset = resp.headers.get_content_charset() or "utf-8"
    except urllib.error.HTTPError as exc:
        raise HTTPError(f"{url} -> HTTP {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise HTTPError(f"{url} -> {exc.reason}") from exc

    html = raw.decode(charset, errors="replace")
    parser = _TextExtractor()
    parser.feed(html)
    return PageReview(url=url, title=parser.title or url, text=parser.text)
