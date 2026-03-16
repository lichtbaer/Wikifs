"""Two-stage cache (In-Memory LRU + SQLite).

Cache-Key-Konvention (von Backend-Clients erzeugt):
  wikidata:entity:{entity_id}           → Entity-Daten
  wikidata:search:{query}:{lang}        → Search-Ergebnisse
  wikidata:sparql:{query_hash}          → SPARQL-Ergebnisse
  wikipedia:summary:{title}:{lang}      → Summary
  wikipedia:article:{title}:{lang}      → Full Article HTML
  wikipedia:sections:{title}:{lang}     → Sections
"""

from __future__ import annotations

import sqlite3
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from wikifs.errors import ErrorCollector
from wikifs.tracing import TraceContext


@dataclass
class CacheConfig:
    """Configuration for the two-level cache."""

    l1_max_size: int = 256
    l1_ttl_seconds: int = 3600
    l2_ttl_seconds: int = 86400
    l2_db_path: str = "~/.wikifs/cache.db"


@dataclass
class CacheStats:
    """Statistics for cache hit/miss and sizes."""

    l1_hits: int
    l1_misses: int
    l2_hits: int
    l2_misses: int
    l1_size: int
    l2_size: int
    hit_rate: float


def _expand_path(path: str) -> Path:
    """Expand user path (e.g. ~/.wikifs/cache.db)."""
    return Path(path).expanduser()


class _L1Cache:
    """In-memory LRU cache with TTL support using OrderedDict."""

    def __init__(self, max_size: int, ttl_seconds: int) -> None:
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        # OrderedDict: (key -> (value, expires_at_iso))
        self._store: OrderedDict[str, tuple[bytes, str]] = OrderedDict()

    def get(self, key: str) -> bytes | None:
        """Get value if present and not expired. Moves to end (most recently used)."""
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if datetime.now(UTC) >= datetime.fromisoformat(expires_at):
            del self._store[key]
            return None
        # Move to end (LRU: most recently used)
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        """Set value with TTL. Evicts oldest if at capacity."""
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl)
        expires_at_iso = expires_at.isoformat()

        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (value, expires_at_iso)

        while len(self._store) > self._max_size:
            self._store.popitem(last=False)

    def delete(self, key: str) -> bool:
        """Delete key. Returns True if key was present."""
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> int:
        """Clear all entries. Returns count of deleted entries."""
        count = len(self._store)
        self._store.clear()
        return count

    def size(self) -> int:
        """Current number of entries."""
        return len(self._store)


class _L2Cache:
    """SQLite-backed cache with lazy expiration cleanup."""

    def __init__(
        self,
        db_path: str,
        ttl_seconds: int,
        error_collector: ErrorCollector | None = None,
    ) -> None:
        self._path = _expand_path(db_path)
        self._ttl_seconds = ttl_seconds
        self._error_collector = error_collector
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self._path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    key TEXT PRIMARY KEY,
                    value BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache_entries(expires_at)"
            )
            conn.commit()

    def get(self, key: str) -> bytes | None:
        """Get value if present and not expired. Lazy-deletes expired on read."""
        now_iso = datetime.now(UTC).isoformat()
        try:
            with sqlite3.connect(self._path) as conn:
                row = conn.execute(
                    "SELECT value, expires_at FROM cache_entries WHERE key = ?", (key,)
                ).fetchone()
                if row is None:
                    return None
                value, expires_at = row[0], row[1]
                if now_iso >= expires_at:
                    conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
                    conn.commit()
                    return None
                return cast(bytes, value)
        except sqlite3.Error as e:
            if self._error_collector:
                self._error_collector.record(
                    category="cache",
                    severity="error",
                    message=f"SQLite error on cache get: {e}",
                    details={"key": key, "error": str(e)},
                )
            raise

    def set(self, key: str, value: bytes, ttl_seconds: int | None = None) -> None:
        """Set value with TTL."""
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl)
        now_iso = now.isoformat()
        expires_at_iso = expires_at.isoformat()
        size_bytes = len(value)

        try:
            with sqlite3.connect(self._path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO cache_entries
                    (key, value, created_at, expires_at, size_bytes)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (key, value, now_iso, expires_at_iso, size_bytes),
                )
                conn.commit()
        except sqlite3.Error as e:
            if self._error_collector:
                self._error_collector.record(
                    category="cache",
                    severity="error",
                    message=f"SQLite error on cache set: {e}",
                    details={"key": key, "error": str(e)},
                )
            raise

    def delete(self, key: str) -> bool:
        """Delete key. Returns True if key was present."""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount > 0

    def clear(self) -> int:
        """Clear all entries. Returns count of deleted entries."""
        with sqlite3.connect(self._path) as conn:
            cursor = conn.execute("DELETE FROM cache_entries")
            count = cursor.rowcount
            conn.commit()
        return count

    def size(self) -> int:
        """Current number of non-expired entries (approximate, may include expired)."""
        now_iso = datetime.now(UTC).isoformat()
        with sqlite3.connect(self._path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM cache_entries WHERE expires_at > ?", (now_iso,)
            ).fetchone()
            return row[0] if row else 0


class Cache:
    """Two-level cache: L1 (In-Memory LRU) → L2 (SQLite)."""

    def __init__(
        self,
        config: CacheConfig,
        error_collector: ErrorCollector | None = None,
    ) -> None:
        self._config = config
        self._l1 = _L1Cache(config.l1_max_size, config.l1_ttl_seconds)
        self._l2 = _L2Cache(
            config.l2_db_path, config.l2_ttl_seconds, error_collector
        )
        self._l1_hits = 0
        self._l1_misses = 0
        self._l2_hits = 0
        self._l2_misses = 0

    def get(self, key: str, ctx: TraceContext | None = None) -> bytes | None:
        """Get value: L1 first, then L2. On L2 hit, promote to L1. Records trace events."""
        # L1 lookup
        value = self._l1.get(key)
        if value is not None:
            self._l1_hits += 1
            if ctx is not None:
                ctx.record_cache_hit()
            return value
        self._l1_misses += 1

        # L2 lookup
        value = self._l2.get(key)
        if value is not None:
            self._l2_hits += 1
            if ctx is not None:
                ctx.record_cache_hit()
            # Promote to L1
            self._l1.set(key, value, self._config.l1_ttl_seconds)
            return value
        self._l2_misses += 1
        if ctx is not None:
            ctx.record_cache_miss()
        return None

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        """Write to both L1 and L2."""
        ttl_sec = ttl if ttl is not None else self._config.l2_ttl_seconds
        self._l1.set(key, value, ttl_sec)
        self._l2.set(key, value, ttl_sec)

    def delete(self, key: str) -> bool:
        """Delete from both levels. Returns True if key was present in either."""
        l1_deleted = self._l1.delete(key)
        l2_deleted = self._l2.delete(key)
        return l1_deleted or l2_deleted

    def clear(self) -> int:
        """Clear both levels. Returns count of deleted entries (L2 as source of truth)."""
        self._l1.clear()
        l2_count = self._l2.clear()
        return l2_count

    def stats(self) -> CacheStats:
        """Return cache statistics."""
        # total_requests = number of get() calls = l1_hits + l2_hits + l2_misses
        total = self._l1_hits + self._l2_hits + self._l2_misses
        hits = self._l1_hits + self._l2_hits
        hit_rate = hits / total if total > 0 else 0.0
        return CacheStats(
            l1_hits=self._l1_hits,
            l1_misses=self._l1_misses,
            l2_hits=self._l2_hits,
            l2_misses=self._l2_misses,
            l1_size=self._l1.size(),
            l2_size=self._l2.size(),
            hit_rate=hit_rate,
        )
