from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AutoAccentAdapter(Protocol):
    """Interface for optional auto-accent implementations."""

    name: str

    def apply(self, text: str) -> str:
        """Return accented text representation."""


@dataclass(frozen=True)
class NoOpAutoAccentAdapter:
    """Fallback adapter that preserves cleaned text as-is."""

    name: str = "noop"

    def apply(self, text: str) -> str:
        return text


def build_auto_accent_adapter(adapter_name: str | None) -> AutoAccentAdapter:
    """Factory for auto-accent adapters.

    For now only a no-op adapter is provided. This keeps extension points explicit
    without blocking runtime in environments where external accentizers are absent.
    """

    normalized = (adapter_name or "noop").strip().lower()
    if normalized in {"", "noop", "none", "disabled"}:
        return NoOpAutoAccentAdapter()

    # Graceful fallback to noop for unknown adapters.
    return NoOpAutoAccentAdapter()
