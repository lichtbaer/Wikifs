"""Tests for Wikipedia nav virtual filename slugs."""

from __future__ import annotations

from wikifs.wikipedia_nav_slug import resolve_nav_slug, title_to_nav_slug


def test_title_to_nav_slug() -> None:
    assert title_to_nav_slug("Kategorie:Berlin") == "Kategorie_Berlin"
    assert title_to_nav_slug("Foo Bar") == "Foo_Bar"


def test_resolve_nav_slug() -> None:
    titles = ["Kategorie:A", "Kategorie:B"]
    assert resolve_nav_slug("Kategorie_A", titles) == "Kategorie:A"
    assert resolve_nav_slug("missing", titles) is None
