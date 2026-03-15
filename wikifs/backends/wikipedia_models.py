"""Wikipedia data models for WikiFS."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArticleSummary:
    """Summary of a Wikipedia article (lead section)."""

    title: str
    extract: str  # Einleitungsabsatz als Plain Text
    extract_markdown: str  # Einleitung als Markdown
    description: str | None  # Wikidata-Kurzbeschreibung
    thumbnail_url: str | None
    page_url: str  # Canonical Wikipedia URL


@dataclass
class ArticleContent:
    """Full Wikipedia article content."""

    title: str
    markdown: str  # Gesamter Artikel als Markdown
    html: str  # Original HTML (für Debugging/Caching)
    word_count: int
    page_url: str


@dataclass
class Section:
    """Single section of a Wikipedia article."""

    title: str  # "Geschichte", "Geographie"
    level: int  # Heading Level (2, 3, 4)
    markdown: str  # Section-Inhalt als Markdown
    anchor: str  # URL-Anchor für Deep Links
