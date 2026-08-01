"""Provider registry.

Only the mock provider ships here. Register your own authorized provider by
adding it to PROVIDERS.
"""

from __future__ import annotations

from .base import RecordsProvider
from .mock import MockProvider

PROVIDERS: dict[str, type[RecordsProvider]] = {
    "mock": MockProvider,
}


def get_provider(name: str) -> RecordsProvider:
    try:
        return PROVIDERS[name]()
    except KeyError:
        available = ", ".join(sorted(PROVIDERS)) or "(none)"
        raise SystemExit(f"Unknown provider {name!r}. Available: {available}")
