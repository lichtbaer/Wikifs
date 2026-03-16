"""Error-Reporting & Run-Export — ErrorStore, ErrorCollector, RunStore."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def _expand_path(path: str) -> Path:
    """Expand user path (e.g. ~/.wikifs/errors.db)."""
    return Path(path).expanduser()


@dataclass
class ErrorEntry:
    """Single error record."""

    error_id: str
    timestamp: str
    trace_id: str | None
    run_id: str | None
    category: str
    severity: str
    command: str | None
    path: str | None
    message: str
    details: dict[str, Any]
    resolved: bool = False


@dataclass
class Run:
    """Single run record (CLI session or Agent run)."""

    run_id: str
    timestamp: str
    type: str
    query: str | None
    trace_ids: list[str]
    error_ids: list[str]
    duration_ms: float
    success: bool
    result: str | None
    model: str | None
    commands_count: int


class ErrorStore:
    """SQLite-backed store for errors."""

    def __init__(self, db_path: str) -> None:
        self._path = _expand_path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS errors (
                    error_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    trace_id TEXT,
                    run_id TEXT,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    command TEXT,
                    path TEXT,
                    message TEXT NOT NULL,
                    details TEXT NOT NULL,
                    resolved INTEGER DEFAULT 0
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON errors(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_category ON errors(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_severity ON errors(severity)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_run_id ON errors(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_errors_resolved ON errors(resolved)")
            conn.commit()

    def insert(self, entry: ErrorEntry) -> None:
        """Insert an error entry."""
        details_json = json.dumps(entry.details)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO errors
                (error_id, timestamp, trace_id, run_id, category, severity,
                 command, path, message, details, resolved)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.error_id,
                    entry.timestamp,
                    entry.trace_id,
                    entry.run_id,
                    entry.category,
                    entry.severity,
                    entry.command,
                    entry.path,
                    entry.message,
                    details_json,
                    1 if entry.resolved else 0,
                ),
            )
            conn.commit()

    def query(
        self,
        since: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        run_id: str | None = None,
        unresolved_only: bool = False,
        limit: int = 100,
    ) -> list[ErrorEntry]:
        """Query errors by filters."""
        conditions: list[str] = []
        params: list[Any] = []
        if since is not None:
            try:
                delta = self._parse_since(since)
                cutoff = (datetime.now(UTC) - delta).isoformat()
                conditions.append("timestamp >= ?")
                params.append(cutoff)
            except ValueError:
                pass
        if category is not None:
            conditions.append("category = ?")
            params.append(category)
        if severity is not None:
            conditions.append("severity = ?")
            params.append(severity)
        if run_id is not None:
            conditions.append("run_id = ?")
            params.append(run_id)
        if unresolved_only:
            conditions.append("resolved = 0")
        params.append(limit)
        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT error_id, timestamp, trace_id, run_id, category, severity,
                   command, path, message, details, resolved
            FROM errors
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        result: list[ErrorEntry] = []
        for row in rows:
            result.append(
                ErrorEntry(
                    error_id=row["error_id"],
                    timestamp=row["timestamp"],
                    trace_id=row["trace_id"],
                    run_id=row["run_id"],
                    category=row["category"],
                    severity=row["severity"],
                    command=row["command"],
                    path=row["path"],
                    message=row["message"],
                    details=json.loads(row["details"]),
                    resolved=bool(row["resolved"]),
                )
            )
        return result

    def _parse_since(self, since: str) -> timedelta:
        """Parse '24h', '7d', '1h' etc. into timedelta."""
        since = since.strip().lower()
        if since.endswith("h"):
            hours = int(since[:-1])
            return timedelta(hours=hours)
        if since.endswith("d"):
            days = int(since[:-1])
            return timedelta(days=days)
        if since.endswith("m"):
            minutes = int(since[:-1])
            return timedelta(minutes=minutes)
        raise ValueError(f"Invalid since format: {since}")

    def summary(self) -> dict[str, dict[str, int]]:
        """Aggregate errors by category and severity."""
        with sqlite3.connect(self._path) as conn:
            rows = conn.execute(
                """
                SELECT category, severity, COUNT(*) as cnt
                FROM errors
                GROUP BY category, severity
                """
            ).fetchall()
        result: dict[str, dict[str, int]] = {}
        for row in rows:
            cat, sev, cnt = row[0], row[1], row[2]
            if cat not in result:
                result[cat] = {}
            result[cat][sev] = cnt
        return result

    def mark_resolved(self, error_id: str) -> bool:
        """Mark error as resolved. Returns True if found."""
        with sqlite3.connect(self._path) as conn:
            conn.execute("UPDATE errors SET resolved = 1 WHERE error_id = ?", (error_id,))
            conn.commit()
            return conn.total_changes > 0

    def get_by_id(self, error_id: str) -> ErrorEntry | None:
        """Fetch single error by ID."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT error_id, timestamp, trace_id, run_id, category, severity,
                       command, path, message, details, resolved
                FROM errors
                WHERE error_id = ?
                """,
                (error_id,),
            ).fetchone()
        if row is None:
            return None
        return ErrorEntry(
            error_id=row["error_id"],
            timestamp=row["timestamp"],
            trace_id=row["trace_id"],
            run_id=row["run_id"],
            category=row["category"],
            severity=row["severity"],
            command=row["command"],
            path=row["path"],
            message=row["message"],
            details=json.loads(row["details"]),
            resolved=bool(row["resolved"]),
        )


class ErrorCollector:
    """Collects errors and records them to ErrorStore."""

    def __init__(self, store: ErrorStore) -> None:
        self._store = store

    def get_error_ids_for_run(self, run_id: str) -> list[str]:
        """Get error IDs for a given run."""
        entries = self._store.query(run_id=run_id, limit=1000)
        return [e.error_id for e in entries]

    def record(
        self,
        category: str,
        severity: str,
        message: str,
        details: dict[str, Any] | None = None,
        trace_id: str | None = None,
        run_id: str | None = None,
        command: str | None = None,
        path: str | None = None,
    ) -> ErrorEntry:
        """Record an error. Returns the created ErrorEntry."""
        entry = ErrorEntry(
            error_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            trace_id=trace_id,
            run_id=run_id,
            category=category,
            severity=severity,
            command=command,
            path=path,
            message=message,
            details=details or {},
        )
        self._store.insert(entry)
        return entry


class RunStore:
    """SQLite-backed store for runs."""

    def __init__(self, db_path: str) -> None:
        self._path = _expand_path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    type TEXT NOT NULL,
                    query TEXT,
                    trace_ids TEXT NOT NULL,
                    error_ids TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    success INTEGER NOT NULL,
                    result TEXT,
                    model TEXT,
                    commands_count INTEGER NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON runs(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_type ON runs(type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_success ON runs(success)")
            conn.commit()

    def insert(self, run: Run) -> None:
        """Insert a run."""
        trace_ids_json = json.dumps(run.trace_ids)
        error_ids_json = json.dumps(run.error_ids)
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                INSERT INTO runs
                (run_id, timestamp, type, query, trace_ids, error_ids,
                 duration_ms, success, result, model, commands_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.timestamp,
                    run.type,
                    run.query,
                    trace_ids_json,
                    error_ids_json,
                    run.duration_ms,
                    1 if run.success else 0,
                    run.result,
                    run.model,
                    run.commands_count,
                ),
            )
            conn.commit()

    def query(
        self,
        failed_only: bool = False,
        run_type: str | None = None,
        since: str | None = None,
        limit: int = 50,
    ) -> list[Run]:
        """Query runs by filters."""
        conditions: list[str] = []
        params: list[Any] = []
        if failed_only:
            conditions.append("success = 0")
        if run_type is not None:
            conditions.append("type = ?")
            params.append(run_type)
        if since is not None:
            try:
                delta = self._parse_since(since)
                cutoff = (datetime.now(UTC) - delta).isoformat()
                conditions.append("timestamp >= ?")
                params.append(cutoff)
            except ValueError:
                pass
        params.append(limit)
        where = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT run_id, timestamp, type, query, trace_ids, error_ids,
                   duration_ms, success, result, model, commands_count
            FROM runs
            WHERE {where}
            ORDER BY timestamp DESC
            LIMIT ?
        """
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_run(row) for row in rows]

    def _parse_since(self, since: str) -> timedelta:
        """Parse '24h', '7d', etc. into timedelta."""
        since = since.strip().lower()
        if since.endswith("h"):
            return timedelta(hours=int(since[:-1]))
        if since.endswith("d"):
            return timedelta(days=int(since[:-1]))
        if since.endswith("m"):
            return timedelta(minutes=int(since[:-1]))
        raise ValueError(f"Invalid since format: {since}")

    def _row_to_run(self, row: sqlite3.Row) -> Run:
        return Run(
            run_id=row["run_id"],
            timestamp=row["timestamp"],
            type=row["type"],
            query=row["query"],
            trace_ids=json.loads(row["trace_ids"]),
            error_ids=json.loads(row["error_ids"]),
            duration_ms=row["duration_ms"],
            success=bool(row["success"]),
            result=row["result"],
            model=row["model"],
            commands_count=row["commands_count"],
        )

    def get_by_id(self, run_id: str) -> Run | None:
        """Fetch single run by ID."""
        with sqlite3.connect(self._path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT run_id, timestamp, type, query, trace_ids, error_ids,
                       duration_ms, success, result, model, commands_count
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)
