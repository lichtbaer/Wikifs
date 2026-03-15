"""Integration tests for handlers with real backend clients."""

from __future__ import annotations

import tempfile
from pathlib import Path

from wikifs.cache import Cache, CacheConfig
from wikifs.config import ApiConfig, load_config
from wikifs.handlers import create_handler_config, create_handlers
from wikifs.interpreter import Interpreter
from wikifs.router import create_default_router
from wikifs.tracing import TraceCollector, TraceStore


def _cache_config(tmp: Path) -> CacheConfig:
    return CacheConfig(
        l1_max_size=64,
        l1_ttl_seconds=60,
        l2_ttl_seconds=300,
        l2_db_path=str(tmp / "cache.db"),
    )


def _create_interpreter(tmp: Path) -> Interpreter:
    config = load_config()
    api_config = ApiConfig.from_dict(config)
    cache = Cache(_cache_config(tmp))
    handler_config = create_handler_config(config)
    handlers = create_handlers(api_config, cache, handler_config)
    trace_store = TraceStore(str(tmp / "traces.db"))
    router = create_default_router()
    collector = TraceCollector()
    return Interpreter(
        router, collector, handlers=handlers, trace_store=trace_store
    )


def test_e2e_ls_entity() -> None:
    """ls /wiki/entities/Frankfurt_am_Main/ returns directory listing."""
    with tempfile.TemporaryDirectory() as tmp:
        interpreter = _create_interpreter(Path(tmp))
        resp = interpreter.execute(
            {
                "command": "ls",
                "path": "/wiki/entities/Frankfurt_am_Main/",
                "flags": [],
            }
        )
        assert resp.exit_code == 0
        assert "article.md" in resp.output
        assert "summary.md" in resp.output
        assert "properties/" in resp.output
        assert "relations/" in resp.output
        assert "sections/" in resp.output
        assert "meta.json" in resp.output


def test_e2e_cat_properties() -> None:
    """cat .../properties/p1082.txt returns population value (P1082=Einwohnerzahl)."""
    with tempfile.TemporaryDirectory() as tmp:
        interpreter = _create_interpreter(Path(tmp))
        resp = interpreter.execute(
            {
                "command": "cat",
                "path": "/wiki/entities/Frankfurt_am_Main/properties/p1082.txt",
                "flags": [],
            }
        )
        assert resp.exit_code == 0
        assert resp.output
        assert any(c.isdigit() for c in resp.output)


def test_e2e_ls_relations() -> None:
    """ls .../relations/ist_teil_von/ returns targets (P131=located in)."""
    with tempfile.TemporaryDirectory() as tmp:
        interpreter = _create_interpreter(Path(tmp))
        resp = interpreter.execute(
            {
                "command": "ls",
                "path": "/wiki/entities/Frankfurt_am_Main/relations/ist_teil_von/",
                "flags": [],
            }
        )
        assert resp.exit_code == 0
        assert "Hessen" in resp.output or "Deutschland" in resp.output or "→" in resp.output


def test_e2e_ls_relations_part_of() -> None:
    """ls .../relations/part_of/ returns Hessen, Deutschland (P131, not P361)."""
    with tempfile.TemporaryDirectory() as tmp:
        interpreter = _create_interpreter(Path(tmp))
        resp = interpreter.execute(
            {
                "command": "ls",
                "path": "/wiki/entities/Frankfurt_am_Main/relations/part_of/",
                "flags": [],
            }
        )
        assert resp.exit_code == 0
        assert "Hessen" in resp.output or "Deutschland" in resp.output or "→" in resp.output


def test_e2e_ls_relations_located_in() -> None:
    """ls .../relations/located_in/ works identically to part_of (both P131)."""
    with tempfile.TemporaryDirectory() as tmp:
        interpreter = _create_interpreter(Path(tmp))
        resp = interpreter.execute(
            {
                "command": "ls",
                "path": "/wiki/entities/Frankfurt_am_Main/relations/located_in/",
                "flags": [],
            }
        )
        assert resp.exit_code == 0
        assert "Hessen" in resp.output or "Deutschland" in resp.output or "→" in resp.output


def test_e2e_cat_summary() -> None:
    """cat .../summary.md returns summary."""
    with tempfile.TemporaryDirectory() as tmp:
        interpreter = _create_interpreter(Path(tmp))
        resp = interpreter.execute(
            {
                "command": "cat",
                "path": "/wiki/entities/Hessen/summary.md",
                "flags": [],
            }
        )
        assert resp.exit_code == 0
        assert len(resp.output) > 100


def test_e2e_search() -> None:
    """search "Goethe" returns results."""
    with tempfile.TemporaryDirectory() as tmp:
        interpreter = _create_interpreter(Path(tmp))
        resp = interpreter.execute(
            {
                "command": "search",
                "path": "/wiki/search",
                "flags": ["--limit", "5"],
                "pattern": "Goethe",
            }
        )
        assert resp.exit_code == 0
        assert "Goethe" in resp.output or "Q" in resp.output


def test_e2e_entity_not_found() -> None:
    """Unknown entity returns suggestions."""
    with tempfile.TemporaryDirectory() as tmp:
        interpreter = _create_interpreter(Path(tmp))
        resp = interpreter.execute(
            {
                "command": "ls",
                "path": "/wiki/entities/XYZZY_Nonexistent_Entity/",
                "flags": [],
            }
        )
        assert resp.exit_code == 2
        assert resp.error_type == "entity_not_found"
