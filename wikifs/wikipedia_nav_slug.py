"""Map Wikipedia page titles to virtual .md filenames under categories/ and links/."""

from __future__ import annotations


def title_to_nav_slug(title: str) -> str:
    """Stable stem for paths: spaces and colons → underscores (matches MediaWiki title quirks)."""
    return title.replace(" ", "_").replace(":", "_")


def resolve_nav_slug(slug: str, titles: list[str]) -> str | None:
    """Find full API title whose slug matches ``slug`` (filename without .md)."""
    for t in titles:
        if title_to_nav_slug(t) == slug:
            return t
    return None
