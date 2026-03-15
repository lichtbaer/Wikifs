"""Tests for two-level cache (L1 + L2)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from wikifs.cache import Cache, CacheConfig
from wikifs.tracing import TraceCollector


def _cache_config(tmp_path: Path) -> CacheConfig:
    return CacheConfig(
        l1_max_size=4,
        l1_ttl_seconds=3600,
        l2_ttl_seconds=86400,
        l2_db_path=str(tmp_path / "cache.db"),
    )


def test_cache_get_set_l1() -> None:
    """Cache.get() checks L1 first; set writes to both levels."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        cache.set("k1", b"v1")
        assert cache.get("k1") == b"v1"
        s = cache.stats()
        assert s.l1_hits == 1
        assert s.l1_misses == 0
        assert s.l2_hits == 0
        assert s.l2_misses == 0


def test_cache_get_l2_promotes_to_l1() -> None:
    """L2 hit promotes entry to L1."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        cache.set("k1", b"v1")
        # Evict from L1 by filling it
        for i in range(5):
            cache.set(f"k{i}", b"x")
        # k1 should be in L2 only now (L1 has k0..k4, k1 evicted)
        # Actually L1 has max 4, so we have k1, k0, k1, k2, k3, k4 - wait
        # After set k0, k1, k2, k3 we have 4. set k4 evicts k0. So L1: k1,k2,k3,k4
        # k1 is still in L1! Let me use more keys to evict k1.
        cache.clear()
        cache.set("k1", b"v1")
        for i in range(10):
            cache.set(f"key{i}", b"x")
        # Now k1 should be evicted from L1
        val = cache.get("k1")
        assert val == b"v1"
        s = cache.stats()
        assert s.l2_hits == 1
        # Second get should hit L1 (promoted)
        val2 = cache.get("k1")
        assert val2 == b"v1"
        assert cache.stats().l1_hits == 1


def test_cache_get_order_l1_then_l2() -> None:
    """Cache.get() checks L1 first, then L2."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        cache.set("a", b"from_both")
        v = cache.get("a")
        assert v == b"from_both"
        s = cache.stats()
        assert s.l1_hits == 1
        assert s.l2_hits == 0


def test_cache_miss_returns_none() -> None:
    """Cache miss returns None."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        assert cache.get("nonexistent") is None
        s = cache.stats()
        assert s.l1_misses == 1
        assert s.l2_misses == 1


def test_cache_set_writes_both_levels() -> None:
    """Cache.set() writes to both L1 and L2."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        cache.set("x", b"data")
        assert cache.get("x") == b"data"
        # Clear L1 only (by creating new Cache - L1 is fresh)
        cache2 = Cache(cfg)
        assert cache2.get("x") == b"data"  # From L2
        s = cache2.stats()
        assert s.l2_hits == 1


def test_cache_ttl_expired_returns_none() -> None:
    """Expired entries return None even if physically present."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = CacheConfig(
            l1_max_size=4,
            l1_ttl_seconds=0,  # Expire immediately
            l2_ttl_seconds=0,
            l2_db_path=str(Path(tmp) / "cache.db"),
        )
        cache = Cache(cfg)
        cache.set("k", b"v")
        assert cache.get("k") is None


def test_cache_l1_eviction_lru() -> None:
    """L1 evicts correctly when exceeding l1_max_size (LRU semantics)."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = CacheConfig(
            l1_max_size=3,
            l1_ttl_seconds=3600,
            l2_ttl_seconds=86400,
            l2_db_path=str(Path(tmp) / "cache.db"),
        )
        cache = Cache(cfg)
        cache.set("a", b"1")
        cache.set("b", b"2")
        cache.set("c", b"3")
        assert cache.get("a") == b"1"
        cache.set("d", b"4")  # Evicts LRU: b. Order was b,c,a after get(a); b evicted.
        # b is in L2, so get(b) returns from L2 (L2 hit), then promotes to L1
        val_b = cache.get("b")
        assert val_b == b"2"
        s = cache.stats()
        assert s.l2_hits == 1  # b was L2 hit (evicted from L1)
        assert cache.get("a") == b"1"
        assert cache.get("c") == b"3"
        assert cache.get("d") == b"4"


def test_cache_stats_counts() -> None:
    """Cache.stats() returns correct hit/miss counts."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        cache.set("h1", b"x")
        cache.get("h1")
        cache.get("h1")
        cache.get("miss")
        s = cache.stats()
        assert s.l1_hits == 2
        assert s.l1_misses == 1
        assert s.l2_misses == 1
        assert s.hit_rate == 2 / 3


def test_cache_clear() -> None:
    """Cache.clear() empties both levels and returns count."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        cache.set("a", b"1")
        cache.set("b", b"2")
        count = cache.clear()
        assert count == 2
        assert cache.get("a") is None
        assert cache.get("b") is None
        s = cache.stats()
        assert s.l1_size == 0
        assert s.l2_size == 0


def test_cache_delete() -> None:
    """Cache.delete() removes from both levels."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        cache.set("k", b"v")
        assert cache.delete("k") is True
        assert cache.get("k") is None
        assert cache.delete("k") is False


def test_cache_trace_integration() -> None:
    """Cache.get() records cache hit/miss when ctx provided."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg = _cache_config(Path(tmp))
        cache = Cache(cfg)
        cache.set("hit", b"x")
        collector = TraceCollector()
        ctx = collector.start_trace("cat", "/path", [])
        with ctx.phase("cache"):
            cache.get("hit", ctx)
        trace = collector.finish_trace(ctx, 0)
        assert trace.cache_hits == 1
        assert trace.cache_misses == 0
        assert trace.phases[0].result == "cache_hit"

        ctx2 = collector.start_trace("cat", "/path", [])
        with ctx2.phase("cache"):
            cache.get("miss_key", ctx2)
        trace2 = collector.finish_trace(ctx2, 0)
        assert trace2.cache_misses == 1
        assert trace2.phases[0].result == "cache_miss"
