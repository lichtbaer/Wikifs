"""Two-stage cache stub (In-Memory LRU + SQLite)."""

from __future__ import annotations


def get(key: str) -> str | None:
    """Retrieve value from cache."""
    raise NotImplementedError


def set_(key: str, value: str) -> None:
    """Store value in cache."""
    raise NotImplementedError
