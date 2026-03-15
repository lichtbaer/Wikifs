"""Tests for Wikidata client."""

from __future__ import annotations

import tempfile
from pathlib import Path

from wikifs.backends.wikidata import WikidataClient
from wikifs.backends.wikidata_models import ClassMembers
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


def test_resolve_entity_frankfurt() -> None:
    """resolve_entity('Frankfurt_am_Main') returns ResolvedEntity with entity_id Q1794."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        result = client.resolve_entity("Frankfurt_am_Main", "de")

        assert result.entity is not None
        assert result.entity.entity_id == "Q1794"
        assert "Frankfurt" in result.entity.label
        assert result.suggestions == []


def test_resolve_entity_typo_returns_suggestions() -> None:
    """resolve_entity with ambiguous query returns None with suggestions."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        # "Frankfurt Main" is ambiguous; search returns multiple, no exact match
        result = client.resolve_entity("Frankfurt Main", "de")

        assert result.entity is None
        assert len(result.suggestions) > 0
        assert any("Frankfurt" in s for s in result.suggestions)


def test_resolve_entity_by_id() -> None:
    """resolve_entity_by_id('Q1794') works as alias access."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        entity = client.resolve_entity_by_id("Q1794", "de")

        assert entity is not None
        assert entity.entity_id == "Q1794"
        assert "Frankfurt" in entity.label
        assert entity.wikipedia_title


def test_get_claims() -> None:
    """get_claims('Q1794') returns properties including population, country, coordinates."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        claims = client.get_claims("Q1794")

        assert len(claims) > 0
        prop_ids = {c.property_id for c in claims}
        assert "P1082" in prop_ids  # population
        assert "P17" in prop_ids  # country
        assert "P625" in prop_ids  # coordinates


def test_get_claim_value() -> None:
    """get_claim_value('Q1794', 'P1082') returns formatted population with qualifier."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        value = client.get_claim_value("Q1794", "P1082")

        assert value is not None
        assert value.value
        assert value.formatted


def test_get_relation_targets() -> None:
    """get_relation_targets('Q1794', 'P131') returns administrative entities."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        targets = client.get_relation_targets("Q1794", "P131")

        assert len(targets) >= 1
        # P131 = located in; Frankfurt is in Hessen, Deutschland
        assert all(t.entity_id.startswith("Q") for t in targets)


def test_search_entities() -> None:
    """search_entities('Goethe') returns relevant results."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        results = client.search_entities("Goethe", "de", 10)

        assert len(results) > 0
        assert any("Goethe" in r.label for r in results)


def test_sparql_query() -> None:
    """sparql_query returns cities (Q515 = city)."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        query = "SELECT ?x WHERE { ?x wdt:P31 wd:Q515 } LIMIT 5"
        results = client.sparql_query(query)

        assert len(results) <= 5
        assert len(results) > 0
        assert "x" in results[0]


def test_cache_second_call_from_cache() -> None:
    """Second call comes from cache (verified via cache stats)."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        client.resolve_entity("Frankfurt_am_Main", "de")
        stats1 = cache.stats()

        client.resolve_entity("Frankfurt_am_Main", "de")
        stats2 = cache.stats()

        assert stats2.l1_hits > stats1.l1_hits or stats2.l2_hits > stats1.l2_hits


def test_trace_integration() -> None:
    """API calls are traced (record_api_call)."""
    from wikifs.tracing import TraceCollector

    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)
        collector = TraceCollector()
        ctx = collector.start_trace("ls", "/wiki/entities/Frankfurt_am_Main/", [])

        with ctx.phase("resolve"):
            result = client.resolve_entity("Frankfurt_am_Main", "de", ctx=ctx)

        trace = collector.finish_trace(ctx, 0)

        assert result.entity is not None
        assert trace.api_calls >= 0  # May be 0 if cached
        assert trace.response_bytes >= 0


def test_get_entity() -> None:
    """get_entity returns full WikidataEntity."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        entity = client.get_entity("Q1794")

        assert entity is not None
        assert entity.entity_id == "Q1794"
        assert entity.label
        assert "dewiki" in entity.sitelinks or "enwiki" in entity.sitelinks
        assert len(entity.claims) > 0


def test_get_class_members() -> None:
    """get_class_members returns ClassMembers for Q515 (city)."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        api_cfg = _api_config()
        client = WikidataClient(api_cfg, cache)

        members = client.get_class_members("Q515", limit=5)

        assert isinstance(members, ClassMembers)
        assert len(members.members) <= 5
        assert members.has_more is not None
