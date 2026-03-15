"""Tests for tracing infrastructure."""

from __future__ import annotations

import tempfile
from pathlib import Path

from wikifs.tracing import (
    Trace,
    TraceCollector,
    TracePhase,
    TraceStore,
)


def test_trace_collector_creates_complete_trace() -> None:
    """TraceCollector produces complete traces with correct duration measurements."""
    collector = TraceCollector()
    ctx = collector.start_trace("cat", "/wiki/entities/Frankfurt/article.md", [])
    with ctx.phase("resolve_entity"):
        pass
    with ctx.phase("fetch_content"):
        pass
    trace = collector.finish_trace(ctx, exit_code=0)
    assert trace.trace_id
    assert trace.request_id
    assert trace.command == "cat"
    assert trace.path == "/wiki/entities/Frankfurt/article.md"
    assert trace.flags == []
    assert len(trace.phases) == 2
    assert trace.phases[0].phase == "resolve_entity"
    assert trace.phases[1].phase == "fetch_content"
    phase_duration_sum = sum(p.duration_ms for p in trace.phases)
    assert abs(trace.total_duration_ms - phase_duration_sum) <= 5


def test_trace_context_phase_as_context_manager() -> None:
    """TraceContext.phase() as context manager measures correctly."""
    collector = TraceCollector()
    ctx = collector.start_trace("ls", "/wiki/", [])
    with ctx.phase("parse"):
        pass
    with ctx.phase("route"):
        pass
    trace = collector.finish_trace(ctx, exit_code=0)
    assert len(trace.phases) == 2
    assert trace.phases[0].phase == "parse"
    assert trace.phases[1].phase == "route"


def test_trace_context_nested_phases() -> None:
    """Nested phases are correctly captured (inner exits first, so inner before outer)."""
    collector = TraceCollector()
    ctx = collector.start_trace("search", "/wiki/", ["--limit", "10"])
    with ctx.phase("outer"):
        with ctx.phase("inner"):
            pass
    trace = collector.finish_trace(ctx, exit_code=0)
    assert len(trace.phases) == 2
    phase_names = [p.phase for p in trace.phases]
    assert "outer" in phase_names
    assert "inner" in phase_names


def test_trace_context_record_cache_hit_miss() -> None:
    """record_cache_hit and record_cache_miss update counters."""
    collector = TraceCollector()
    ctx = collector.start_trace("cat", "/path", [])
    with ctx.phase("fetch"):
        ctx.record_cache_hit()
    with ctx.phase("resolve"):
        ctx.record_cache_miss()
    trace = collector.finish_trace(ctx, exit_code=0)
    assert trace.cache_hits == 1
    assert trace.cache_misses == 1


def test_trace_context_record_api_call() -> None:
    """record_api_call updates counters and phase info."""
    collector = TraceCollector()
    ctx = collector.start_trace("cat", "/path", [])
    with ctx.phase("fetch"):
        ctx.record_api_call("https://example.com/api", 1024)
    trace = collector.finish_trace(ctx, exit_code=0)
    assert trace.api_calls == 1
    assert trace.response_bytes == 1024
    assert trace.phases[0].api_url == "https://example.com/api"
    assert trace.phases[0].response_bytes == 1024


def test_trace_store_save_and_query() -> None:
    """TraceStore.save persists to SQLite, query finds traces."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "traces.db"
        store = TraceStore(str(db_path))
        trace = Trace(
            trace_id="tid-1",
            request_id="req-1",
            timestamp="2025-01-01T12:00:00Z",
            command="cat",
            path="/wiki/entities/Frankfurt/article.md",
            flags=[],
            phases=[TracePhase("fetch", 10.0, "ok")],
            total_duration_ms=50.0,
            cache_hits=0,
            cache_misses=1,
            api_calls=1,
            response_bytes=1024,
            exit_code=0,
        )
        store.save(trace)
        trace2 = Trace(
            trace_id="tid-2",
            request_id="req-2",
            timestamp="2025-01-01T12:01:00Z",
            command="ls",
            path="/wiki/",
            flags=[],
            phases=[TracePhase("route", 5.0, "ok")],
            total_duration_ms=150.0,
            cache_hits=1,
            cache_misses=0,
            api_calls=0,
            response_bytes=0,
            exit_code=0,
        )
        store.save(trace2)
        result = store.query(min_duration_ms=100.0)
        assert len(result) == 1
        assert result[0].trace_id == "tid-2"
        assert result[0].total_duration_ms == 150.0
        result_cmd = store.query(command="cat")
        assert len(result_cmd) == 1
        assert result_cmd[0].command == "cat"
        result_path = store.query(path_pattern="/wiki/entities/%")
        assert len(result_path) == 1
        assert "Frankfurt" in result_path[0].path


def test_trace_store_stats() -> None:
    """TraceStore.stats returns correct aggregates."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "traces.db"
        store = TraceStore(str(db_path))
        for i, (dur, hits, misses) in enumerate(
            [(10.0, 1, 0), (20.0, 0, 1), (30.0, 1, 0), (40.0, 0, 1), (50.0, 1, 0)]
        ):
            trace = Trace(
                trace_id=f"tid-{i}",
                request_id=f"req-{i}",
                timestamp="2025-01-01T12:00:00Z",
                command="cat",
                path="/path",
                flags=[],
                phases=[TracePhase("fetch", dur, "ok")],
                total_duration_ms=dur,
                cache_hits=hits,
                cache_misses=misses,
                api_calls=0,
                response_bytes=0,
                exit_code=0,
            )
            store.save(trace)
        s = store.stats()
        assert s.count == 5
        assert s.avg_duration_ms == 30.0
        assert s.max_duration_ms == 50.0
        assert s.cache_hit_rate == 0.6  # 3 hits / 5 total
        assert s.commands_by_type == {"cat": 5}


def test_trace_store_clear() -> None:
    """TraceStore.clear deletes traces."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "traces.db"
        store = TraceStore(str(db_path))
        trace = Trace(
            trace_id="tid-1",
            request_id="req-1",
            timestamp="2025-01-01T12:00:00Z",
            command="cat",
            path="/path",
            flags=[],
            phases=[],
            total_duration_ms=10.0,
            cache_hits=0,
            cache_misses=0,
            api_calls=0,
            response_bytes=0,
            exit_code=0,
        )
        store.save(trace)
        assert store.stats().count == 1
        deleted = store.clear(older_than_days=0)
        assert deleted == 1
        assert store.stats().count == 0
        store.save(trace)
        deleted_all = store.clear()
        assert deleted_all == 1


def test_trace_store_stats_empty() -> None:
    """TraceStore.stats returns zeros for empty store."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "traces.db"
        store = TraceStore(str(db_path))
        s = store.stats()
        assert s.count == 0
        assert s.avg_duration_ms == 0.0
        assert s.cache_hit_rate == 0.0
        assert s.commands_by_type == {}


def test_trace_store_query_slow_filter() -> None:
    """Query with min_duration_ms filters correctly (--slow)."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "traces.db"
        store = TraceStore(str(db_path))
        for i, dur in enumerate([10.0, 50.0, 100.0, 150.0]):
            trace = Trace(
                trace_id=f"tid-{i}",
                request_id=f"req-{i}",
                timestamp="2025-01-01T12:00:00Z",
                command="cat",
                path="/path",
                flags=[],
                phases=[TracePhase("fetch", dur, "ok")],
                total_duration_ms=dur,
                cache_hits=0,
                cache_misses=0,
                api_calls=0,
                response_bytes=0,
                exit_code=0,
            )
            store.save(trace)
        result = store.query(min_duration_ms=100.0)
        assert len(result) == 2
        assert all(t.total_duration_ms >= 100.0 for t in result)
