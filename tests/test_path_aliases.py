"""Tests for Q-ID path rewriting."""

from __future__ import annotations

from unittest.mock import MagicMock

from wikifs.backends.wikidata_models import ResolvedEntity
from wikifs.path_aliases import rewrite_entity_qid_path
from wikifs.tracing import TraceCollector


def test_rewrite_qid_replaces_with_wikipedia_title() -> None:
    """Q-ID in path is replaced by underscore Wikipedia title."""
    wikidata = MagicMock()
    wikidata.resolve_entity_by_id.return_value = ResolvedEntity(
        entity_id="Q64",
        label="Berlin",
        description="capital",
        wikipedia_title="Berlin",
        aliases=[],
    )
    collector = TraceCollector()
    ctx = collector.start_trace("ls", "/wiki/entities/Q64/", [], "req-1")

    out = rewrite_entity_qid_path("/wiki/entities/Q64/", wikidata, "de", ctx)

    assert out == "/wiki/entities/Berlin/"
    wikidata.resolve_entity_by_id.assert_called_once_with("Q64", lang="de", ctx=ctx)


def test_rewrite_qid_preserves_suffix() -> None:
    """Property path suffix is kept after Q-ID rewrite."""
    wikidata = MagicMock()
    wikidata.resolve_entity_by_id.return_value = ResolvedEntity(
        entity_id="Q64",
        label="Berlin",
        description="",
        wikipedia_title="Berlin",
        aliases=[],
    )
    collector = TraceCollector()
    ctx = collector.start_trace("cat", "/wiki/entities/Q64/article.md", [], "req-1")

    out = rewrite_entity_qid_path("/wiki/entities/Q64/article.md", wikidata, "en", ctx)

    assert out == "/wiki/entities/Berlin/article.md"


def test_rewrite_non_qid_unchanged() -> None:
    """Human-readable entity paths are not modified."""
    wikidata = MagicMock()
    collector = TraceCollector()
    ctx = collector.start_trace("ls", "/wiki/entities/Paris/", [], "req-1")

    out = rewrite_entity_qid_path("/wiki/entities/Paris/", wikidata, "de", ctx)

    assert out == "/wiki/entities/Paris/"
    wikidata.resolve_entity_by_id.assert_not_called()


def test_rewrite_unresolved_qid_unchanged() -> None:
    """Unknown Q-ID leaves path unchanged (routing may still fail)."""
    wikidata = MagicMock()
    wikidata.resolve_entity_by_id.return_value = None
    collector = TraceCollector()
    ctx = collector.start_trace("ls", "/wiki/entities/Q999999999/", [], "req-1")

    out = rewrite_entity_qid_path("/wiki/entities/Q999999999/", wikidata, "de", ctx)

    assert out == "/wiki/entities/Q999999999/"
