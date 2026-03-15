"""Tests for Wikipedia client."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from wikifs.backends.wikipedia import (
    WikipediaClient,
    WikipediaError,
    WikipediaNotFoundError,
)
from wikifs.backends.wikipedia_models import ArticleContent, ArticleSummary, Section
from wikifs.cache import Cache, CacheConfig
from wikifs.config import ApiConfig


def _api_config() -> ApiConfig:
    return ApiConfig(
        wikidata_base_url="https://www.wikidata.org",
        wikipedia_base_url="https://{lang}.wikipedia.org",
        request_timeout_seconds=10,
        user_agent="WikiFS/0.1 (https://github.com/Lichtbaer/wikifs)",
    )


def _cache_config(tmp_path: Path) -> CacheConfig:
    return CacheConfig(
        l1_max_size=64,
        l1_ttl_seconds=3600,
        l2_ttl_seconds=86400,
        l2_db_path=str(tmp_path / "cache.db"),
    )


def test_get_summary_frankfurt() -> None:
    """get_summary returns ArticleSummary with non-empty extract_markdown."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)

        result = client.get_summary("Frankfurt_am_Main", "de")

        assert isinstance(result, ArticleSummary)
        assert result.title
        assert result.extract
        assert result.extract_markdown
        assert "Frankfurt" in result.extract or "Frankfurt" in result.extract_markdown
        assert result.page_url


def test_get_article_frankfurt_de() -> None:
    """get_article('Frankfurt_am_Main', 'de') returns ArticleContent with clean markdown."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)

        result = client.get_article("Frankfurt_am_Main", "de")

        assert isinstance(result, ArticleContent)
        assert result.title
        assert result.markdown
        assert result.html
        assert result.word_count > 0
        assert result.page_url
        # No raw HTML tags in markdown
        assert "<div>" not in result.markdown
        assert "<span>" not in result.markdown
        assert "<script>" not in result.markdown


def test_get_article_frankfurt_en() -> None:
    """get_article('Frankfurt_am_Main', 'en') returns English article."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)

        result = client.get_article("Frankfurt_am_Main", "en")

        assert isinstance(result, ArticleContent)
        assert result.title
        assert result.markdown
        # English content
        assert "Frankfurt" in result.markdown or "Germany" in result.markdown


def test_get_sections_frankfurt() -> None:
    """get_sections returns list of sections with correct titles and levels."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)

        sections = client.get_sections("Frankfurt_am_Main", "de")

        assert isinstance(sections, list)
        assert len(sections) > 0
        for s in sections:
            assert isinstance(s, Section)
            assert s.title
            assert s.level in (2, 3, 4)
            assert s.anchor
            assert s.markdown is not None
        # Frankfurt article has "Geschichte" section
        titles = [s.title for s in sections]
        assert "Geschichte" in titles or any("Geschichte" in t for t in titles)


def test_get_section_geschichte() -> None:
    """get_section('Frankfurt_am_Main', 'Geschichte', 'de') returns single section."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)

        section = client.get_section("Frankfurt_am_Main", "Geschichte", "de")

        assert section is not None
        assert section.title == "Geschichte"
        assert section.level == 2
        assert section.anchor
        assert section.markdown


def test_get_section_nonexistent() -> None:
    """get_section('Frankfurt_am_Main', 'Nonexistent', 'de') returns None."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)

        section = client.get_section("Frankfurt_am_Main", "Nonexistent", "de")

        assert section is None


def test_markdown_no_reference_numbers() -> None:
    """Markdown output contains no Wikipedia reference numbers [1], [2]."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)

        result = client.get_article("Frankfurt_am_Main", "de")

        # Reference pattern like [1] or [23] should not appear
        ref_match = re.search(r"\[\d+\]", result.markdown)
        assert ref_match is None, f"Found reference number: {ref_match.group()}"


def test_caching_second_call_from_cache() -> None:
    """All calls cached — second call comes from cache."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)

        r1 = client.get_summary("Frankfurt_am_Main", "de")
        r2 = client.get_summary("Frankfurt_am_Main", "de")

        assert r1.extract == r2.extract
        stats = cache.stats()
        assert stats.l1_hits + stats.l2_hits >= 1


def test_trace_integration() -> None:
    """All API calls traced."""
    from wikifs.tracing import TraceCollector, TraceStore

    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)
        collector = TraceCollector()
        store = TraceStore(str(Path(tmp) / "traces.db"))

        ctx = collector.start_trace("cat", "/Frankfurt_am_Main/article.md", [])
        client.get_summary("Frankfurt_am_Main", "de", ctx)
        trace = collector.finish_trace(ctx, 0)
        store.save(trace)

        assert trace.api_calls >= 1 or trace.cache_hits >= 1


def test_http_404_structured_error() -> None:
    """HTTP 404 produces structured error, no crash."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikipediaClient(api_cfg, cache)

        try:
            client.get_summary("ThisArticleDefinitelyDoesNotExist12345XYZ", "de")
            assert False, "Expected WikipediaNotFoundError"
        except WikipediaNotFoundError as e:
            assert "not found" in str(e).lower() or "404" in str(e)
        except WikipediaError:
            pass  # Any WikipediaError is acceptable
