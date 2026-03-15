"""Tracing infrastructure for WikiFS — SQLite-based trace collection and storage."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class TracePhase:
    """Single phase within a trace."""

    phase: str
    duration_ms: float
    result: str  # "ok", "error", "cache_hit", "cache_miss"
    cache_hit: bool | None = None
    api_url: str | None = None
    response_bytes: int | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class Trace:
    """Complete trace of a command execution."""

    trace_id: str
    request_id: str
    timestamp: str
    command: str
    path: str
    flags: list[str]
    phases: list[TracePhase]
    total_duration_ms: float
    cache_hits: int
    cache_misses: int
    api_calls: int
    response_bytes: int
    exit_code: int


@dataclass
class TraceStats:
    """Aggregate statistics over traces."""

    count: int
    avg_duration_ms: float
    p50_duration_ms: float
    p95_duration_ms: float
    max_duration_ms: float
    cache_hit_rate: float
    commands_by_type: dict[str, int]


class PhaseContext:
    """Context manager for measuring a single phase duration."""

    def __init__(self, ctx: TraceContext, name: str) -> None:
        self._ctx = ctx
        self._name = name
        self._start: float = 0.0
        self._result = "ok"
        self._cache_hit: bool | None = None
        self._api_url: str | None = None
        self._response_bytes = 0
        self._error: str | None = None
        self._metadata: dict[str, Any] | None = None

    def __enter__(self) -> PhaseContext:
        self._start = time.perf_counter()
        self._ctx._current_phase = self
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        self._ctx._current_phase = None
        duration_ms = (time.perf_counter() - self._start) * 1000
        if exc_type is not None:
            self._result = "error"
            self._error = str(exc_val) if exc_val else repr(exc_type)
        phase = TracePhase(
            phase=self._name,
            duration_ms=duration_ms,
            result=self._result,
            cache_hit=self._cache_hit,
            api_url=self._api_url,
            response_bytes=self._response_bytes if self._response_bytes else None,
            error=self._error,
            metadata=self._metadata,
        )
        self._ctx._phases.append(phase)

    def set_result(self, result: str) -> None:
        """Set phase result (ok, error, cache_hit, cache_miss)."""
        self._result = result

    def set_cache_hit(self, hit: bool) -> None:
        """Mark cache hit/miss for this phase."""
        self._cache_hit = hit

    def set_api_call(self, url: str, response_bytes: int) -> None:
        """Record API call for this phase (additive if multiple)."""
        self._api_url = url
        self._response_bytes += response_bytes

    def set_error(self, error: str) -> None:
        """Set error message for this phase."""
        self._error = error

    def set_metadata(self, metadata: dict[str, Any]) -> None:
        """Set additional metadata for this phase."""
        self._metadata = metadata


class TraceContext:
    """Context for a trace with phase measurement and counters."""

    def __init__(
        self,
        trace_id: str,
        request_id: str,
        command: str,
        path: str,
        flags: list[str],
    ) -> None:
        self._trace_id = trace_id
        self._request_id = request_id
        self._command = command
        self._path = path
        self._flags = flags
        self._start = time.perf_counter()
        self._phases: list[TracePhase] = []
        self._cache_hits = 0
        self._cache_misses = 0
        self._api_calls = 0
        self._response_bytes = 0
        self._exit_code = 0
        self._current_phase: PhaseContext | None = None

    @contextmanager
    def phase(self, name: str) -> Generator[PhaseContext, None, None]:
        """Context manager for measuring a phase. Yields PhaseContext."""
        pc = PhaseContext(self, name)
        with pc:
            yield pc

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self._cache_hits += 1
        if self._current_phase is not None:
            self._current_phase.set_cache_hit(True)

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self._cache_misses += 1
        if self._current_phase is not None:
            self._current_phase.set_cache_hit(False)

    def record_api_call(self, url: str, response_bytes: int) -> None:
        """Record an API call with URL and response size."""
        self._api_calls += 1
        self._response_bytes += response_bytes
        if self._current_phase is not None:
            self._current_phase.set_api_call(url, response_bytes)


class TraceCollector:
    """Collects traces and provides TraceContext for phase measurement."""

    def __init__(self) -> None:
        pass

    def start_trace(
        self,
        command: str,
        path: str,
        flags: list[str],
        request_id: str | None = None,
    ) -> TraceContext:
        """Start a new trace. Returns TraceContext for phase measurement."""
        trace_id = str(uuid.uuid4())
        rid = request_id or str(uuid.uuid4())
        return TraceContext(
            trace_id=trace_id,
            request_id=rid,
            command=command,
            path=path,
            flags=flags,
        )

    def finish_trace(self, ctx: TraceContext, exit_code: int) -> Trace:
        """Finish the trace and return the completed Trace."""
        total_duration_ms = (time.perf_counter() - ctx._start) * 1000
        ctx._exit_code = exit_code
        return Trace(
            trace_id=ctx._trace_id,
            request_id=ctx._request_id,
            timestamp=datetime.now(UTC).isoformat(),
            command=ctx._command,
            path=ctx._path,
            flags=ctx._flags,
            phases=ctx._phases.copy(),
            total_duration_ms=total_duration_ms,
            cache_hits=ctx._cache_hits,
            cache_misses=ctx._cache_misses,
            api_calls=ctx._api_calls,
            response_bytes=ctx._response_bytes,
            exit_code=exit_code,
        )


def _expand_path(path: str) -> Path:
    """Expand user path (e.g. ~/.wikifs/traces.db)."""
    return Path(path).expanduser()


def _phase_to_dict(p: TracePhase) -> dict[str, Any]:
    return {
        "phase": p.phase,
        "duration_ms": p.duration_ms,
        "result": p.result,
        "cache_hit": p.cache_hit,
        "api_url": p.api_url,
        "response_bytes": p.response_bytes,
        "error": p.error,
        "metadata": p.metadata,
    }


def _dict_to_phase(d: dict[str, Any]) -> TracePhase:
    return TracePhase(
        phase=d["phase"],
        duration_ms=d["duration_ms"],
        result=d["result"],
        cache_hit=d.get("cache_hit"),
        api_url=d.get("api_url"),
        response_bytes=d.get("response_bytes"),
        error=d.get("error"),
        metadata=d.get("metadata"),
    )


class TraceStore:
    """SQLite-backed store for traces."""

    def __init__(self, db_path: str) -> None:
        self._path = _expand_path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS traces (
                    trace_id TEXT PRIMARY KEY,
                    request_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    command TEXT NOT NULL,
                    path TEXT NOT NULL,
                    flags TEXT NOT NULL,
                    phases TEXT NOT NULL,
                    total_duration_ms REAL NOT NULL,
                    cache_hits INTEGER NOT NULL,
                    cache_misses INTEGER NOT NULL,
                    api_calls INTEGER NOT NULL,
                    response_bytes INTEGER NOT NULL,
                    exit_code INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_traces_timestamp ON traces(timestamp)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_traces_command ON traces(command)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_traces_duration ON traces(total_duration_ms)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_traces_path ON traces(path)"
            )
            conn.commit()

    def save(self, trace: Trace) -> None:
        """Persist a trace to SQLite."""
        phases_json = json.dumps([_phase_to_dict(p) for p in trace.phases])
        flags_json = json.dumps(trace.flags)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO traces
                (trace_id, request_id, timestamp, command, path, flags, phases,
                 total_duration_ms, cache_hits, cache_misses, api_calls,
                 response_bytes, exit_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.trace_id,
                    trace.request_id,
                    trace.timestamp,
                    trace.command,
                    trace.path,
                    flags_json,
                    phases_json,
                    trace.total_duration_ms,
                    trace.cache_hits,
                    trace.cache_misses,
                    trace.api_calls,
                    trace.response_bytes,
                    trace.exit_code,
                ),
            )
            conn.commit()

    def query(
        self,
        min_duration_ms: float | None = None,
        command: str | None = None,
        path_pattern: str | None = None,
        limit: int = 50,
    ) -> list[Trace]:
        """Query traces by filters. Returns list of Trace, sorted by duration desc."""
        conditions: list[str] = []
        params: list[Any] = []
        if min_duration_ms is not None:
            conditions.append("total_duration_ms >= ?")
            params.append(min_duration_ms)
        if command is not None:
            conditions.append("command = ?")
            params.append(command)
        if path_pattern is not None:
            conditions.append("path LIKE ?")
            params.append(path_pattern)
        params.append(limit)
        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT trace_id, request_id, timestamp, command, path, flags, phases,
                   total_duration_ms, cache_hits, cache_misses, api_calls,
                   response_bytes, exit_code
            FROM traces
            WHERE {where}
            ORDER BY total_duration_ms DESC
            LIMIT ?
        """
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        result: list[Trace] = []
        for row in rows:
            phases_data = json.loads(row["phases"])
            phases = [_dict_to_phase(d) for d in phases_data]
            result.append(
                Trace(
                    trace_id=row["trace_id"],
                    request_id=row["request_id"],
                    timestamp=row["timestamp"],
                    command=row["command"],
                    path=row["path"],
                    flags=json.loads(row["flags"]),
                    phases=phases,
                    total_duration_ms=row["total_duration_ms"],
                    cache_hits=row["cache_hits"],
                    cache_misses=row["cache_misses"],
                    api_calls=row["api_calls"],
                    response_bytes=row["response_bytes"],
                    exit_code=row["exit_code"],
                )
            )
        return result

    def stats(self) -> TraceStats:
        """Compute aggregate statistics over all traces."""
        with sqlite3.connect(self._path) as conn:
            count_row = conn.execute("SELECT COUNT(*) as c FROM traces").fetchone()
            count = count_row[0] if count_row else 0

            if count == 0:
                return TraceStats(
                    count=0,
                    avg_duration_ms=0.0,
                    p50_duration_ms=0.0,
                    p95_duration_ms=0.0,
                    max_duration_ms=0.0,
                    cache_hit_rate=0.0,
                    commands_by_type={},
                )

            agg = conn.execute(
                """
                SELECT
                    AVG(total_duration_ms) as avg_dur,
                    MAX(total_duration_ms) as max_dur,
                    SUM(cache_hits) as total_hits,
                    SUM(cache_misses) as total_misses
                FROM traces
                """
            ).fetchone()

            avg_dur = agg[0] or 0.0
            max_dur = agg[1] or 0.0
            total_hits = agg[2] or 0
            total_misses = agg[3] or 0
            total_cache = total_hits + total_misses
            cache_hit_rate = total_hits / total_cache if total_cache > 0 else 0.0

            p50_offset = count // 2
            p50_row = conn.execute(
                """
                SELECT total_duration_ms FROM traces
                ORDER BY total_duration_ms
                LIMIT 1 OFFSET ?
                """,
                (p50_offset,),
            ).fetchone()
            p50_dur = p50_row[0] if p50_row else 0.0

            p95_offset = max(0, min(int(count * 0.95), count) - 1)
            p95_row = conn.execute(
                """
                SELECT total_duration_ms FROM traces
                ORDER BY total_duration_ms
                LIMIT 1 OFFSET ?
                """,
                (p95_offset,),
            ).fetchone()
            p95_dur = p95_row[0] if p95_row else 0.0

            cmd_rows = conn.execute(
                "SELECT command, COUNT(*) as c FROM traces GROUP BY command"
            ).fetchall()
            commands_by_type = {row[0]: row[1] for row in cmd_rows}

        return TraceStats(
            count=count,
            avg_duration_ms=avg_dur,
            p50_duration_ms=p50_dur,
            p95_duration_ms=p95_dur,
            max_duration_ms=max_dur,
            cache_hit_rate=cache_hit_rate,
            commands_by_type=commands_by_type,
        )

    def clear(self, older_than_days: int | None = None) -> int:
        """Delete traces. If older_than_days is None or 0, delete all. Returns deleted count."""
        with sqlite3.connect(self._path) as conn:
            if older_than_days is not None and older_than_days > 0:
                conn.execute(
                    """
                    DELETE FROM traces
                    WHERE date(timestamp) < date('now', ? || ' days')
                    """,
                    (f"-{older_than_days}",),
                )
            else:
                conn.execute("DELETE FROM traces")
            deleted = conn.total_changes
            conn.commit()
        return deleted
