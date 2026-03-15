"""Tests for ErrorStore, ErrorCollector, RunStore."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from wikifs.errors import ErrorCollector, ErrorEntry, ErrorStore, Run, RunStore


@pytest.fixture
def temp_db() -> str:
    """Create temp db path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


def test_error_store_insert_and_query(temp_db: str) -> None:
    """ErrorStore inserts and queries errors."""
    store = ErrorStore(temp_db)
    entry = ErrorEntry(
        error_id="e1",
        timestamp="2025-01-01T12:00:00+00:00",
        trace_id="t1",
        run_id="r1",
        category="api",
        severity="error",
        command="cat",
        path="/wiki/entities/Foo/article.md",
        message="HTTP 503",
        details={"status_code": 503},
    )
    store.insert(entry)
    results = store.query(limit=10)
    assert len(results) == 1
    assert results[0].error_id == "e1"
    assert results[0].category == "api"
    assert results[0].details["status_code"] == 503


def test_error_collector_record(temp_db: str) -> None:
    """ErrorCollector.record creates and persists ErrorEntry."""
    store = ErrorStore(temp_db)
    collector = ErrorCollector(store)
    entry = collector.record(
        category="timeout",
        severity="error",
        message="Request timeout",
        details={"url": "https://example.com"},
        trace_id="t1",
        command="cat",
    )
    assert entry.error_id
    assert entry.category == "timeout"
    results = store.query(limit=10)
    assert len(results) == 1


def test_error_store_summary(temp_db: str) -> None:
    """ErrorStore.summary aggregates by category and severity."""
    store = ErrorStore(temp_db)
    for i in range(3):
        store.insert(
            ErrorEntry(
                error_id=f"e{i}",
                timestamp="2025-01-01T12:00:00+00:00",
                trace_id=None,
                run_id=None,
                category="api",
                severity="error",
                command=None,
                path=None,
                message=f"Error {i}",
                details={},
            )
        )
    store.insert(
        ErrorEntry(
            error_id="e4",
            timestamp="2025-01-01T12:00:00+00:00",
            trace_id=None,
            run_id=None,
            category="cache",
            severity="warning",
            command=None,
            path=None,
            message="Cache error",
            details={},
        )
    )
    summary = store.summary()
    assert summary["api"]["error"] == 3
    assert summary["cache"]["warning"] == 1


def test_error_store_mark_resolved(temp_db: str) -> None:
    """ErrorStore.mark_resolved updates resolved flag."""
    store = ErrorStore(temp_db)
    store.insert(
        ErrorEntry(
            error_id="e1",
            timestamp="2025-01-01T12:00:00+00:00",
            trace_id=None,
            run_id=None,
            category="api",
            severity="error",
            command=None,
            path=None,
            message="Test",
            details={},
        )
    )
    ok = store.mark_resolved("e1")
    assert ok
    entry = store.get_by_id("e1")
    assert entry is not None
    assert entry.resolved


def test_run_store_insert_and_query(temp_db: str) -> None:
    """RunStore inserts and queries runs."""
    store = RunStore(temp_db)
    run = Run(
        run_id="r1",
        timestamp="2025-01-01T12:00:00+00:00",
        type="cli",
        query="ls /wiki/entities/Berlin",
        trace_ids=["t1"],
        error_ids=[],
        duration_ms=100.0,
        success=True,
        result="article.md\nproperties/",
        model=None,
        commands_count=1,
    )
    store.insert(run)
    results = store.query(limit=10)
    assert len(results) == 1
    assert results[0].run_id == "r1"
    assert results[0].type == "cli"
    assert results[0].success


def test_run_store_get_by_id(temp_db: str) -> None:
    """RunStore.get_by_id returns single run."""
    store = RunStore(temp_db)
    run = Run(
        run_id="r1",
        timestamp="2025-01-01T12:00:00+00:00",
        type="agent",
        query="What is Berlin?",
        trace_ids=["t1", "t2"],
        error_ids=["e1"],
        duration_ms=500.0,
        success=False,
        result=None,
        model="openai:gpt-4o",
        commands_count=2,
    )
    store.insert(run)
    found = store.get_by_id("r1")
    assert found is not None
    assert found.run_id == "r1"
    assert found.type == "agent"
    assert found.error_ids == ["e1"]
