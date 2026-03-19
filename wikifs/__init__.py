"""WikiFS — Virtual Filesystem over Wikipedia & Wikidata."""

from __future__ import annotations

__version__ = "0.1.0"

from dataclasses import dataclass

from wikifs.cache import Cache, CacheConfig, CacheStats
from wikifs.config import ApiConfig, load_config
from wikifs.errors import ErrorCollector, ErrorEntry, ErrorStore, Run, RunStore
from wikifs.handlers import create_handler_config, create_handlers
from wikifs.interpreter import Interpreter
from wikifs.models import Command, CommandResponse
from wikifs.path_aliases import rewrite_entity_qid_path
from wikifs.router import RouteMatch, Router, create_default_router, normalize_path
from wikifs.tracing import (
    Trace,
    TraceCollector,
    TraceContext,
    TracePhase,
    TraceStats,
    TraceStore,
)


def create_interpreter(
    config_path: str | None = None,
) -> Interpreter:
    """Create fully wired Interpreter with handlers and trace persistence."""
    config = load_config(config_path)
    api_config = ApiConfig.from_dict(config)
    errors_cfg = config.get("errors", {})
    errors_db = str(errors_cfg.get("db_path", "~/.wikifs/errors.db"))
    error_store = ErrorStore(errors_db)
    run_store = RunStore(errors_db)
    error_collector = ErrorCollector(error_store)
    cache_cfg = config.get("cache", {})
    cache = Cache(
        CacheConfig(
            l1_max_size=int(cache_cfg.get("l1_max_size", 256)),
            l1_ttl_seconds=int(cache_cfg.get("l1_ttl_seconds", 3600)),
            l2_ttl_seconds=int(cache_cfg.get("l2_ttl_seconds", 86400)),
            l2_db_path=str(cache_cfg.get("l2_db_path", "~/.wikifs/cache.db")),
        ),
        error_collector=error_collector,
    )
    handler_config = create_handler_config(config)
    handlers, wikidata = create_handlers(
        api_config, cache, handler_config, error_collector
    )

    def _path_rewriter(path: str, ctx: TraceContext) -> str:
        return rewrite_entity_qid_path(
            path, wikidata, ctx.effective_language(handler_config.default_language), ctx
        )

    trace_cfg = config.get("tracing", {})
    trace_store = TraceStore(str(trace_cfg.get("db_path", "~/.wikifs/traces.db")))
    router = create_default_router()
    collector = TraceCollector()
    return Interpreter(
        router,
        collector,
        handlers=handlers,
        trace_store=trace_store,
        error_collector=error_collector,
        run_store=run_store,
        path_rewriter=_path_rewriter,
        supported_languages=handler_config.supported_languages,
    )


@dataclass
class ServerContext:
    """Context for HTTP server: interpreter, cache, trace_store, error_store, run_store."""

    interpreter: Interpreter
    cache: Cache
    trace_store: TraceStore
    error_store: ErrorStore
    run_store: RunStore


def create_interpreter_with_components(
    config_path: str | None = None,
) -> ServerContext:
    """Create interpreter with cache and trace_store for HTTP server use."""
    config = load_config(config_path)
    api_config = ApiConfig.from_dict(config)
    errors_cfg = config.get("errors", {})
    errors_db = str(errors_cfg.get("db_path", "~/.wikifs/errors.db"))
    error_store = ErrorStore(errors_db)
    run_store = RunStore(errors_db)
    error_collector = ErrorCollector(error_store)
    cache_cfg = config.get("cache", {})
    cache = Cache(
        CacheConfig(
            l1_max_size=int(cache_cfg.get("l1_max_size", 256)),
            l1_ttl_seconds=int(cache_cfg.get("l1_ttl_seconds", 3600)),
            l2_ttl_seconds=int(cache_cfg.get("l2_ttl_seconds", 86400)),
            l2_db_path=str(cache_cfg.get("l2_db_path", "~/.wikifs/cache.db")),
        ),
        error_collector=error_collector,
    )
    handler_config = create_handler_config(config)
    handlers, wikidata = create_handlers(
        api_config, cache, handler_config, error_collector
    )

    def _path_rewriter_srv(path: str, ctx: TraceContext) -> str:
        return rewrite_entity_qid_path(
            path, wikidata, ctx.effective_language(handler_config.default_language), ctx
        )

    trace_cfg = config.get("tracing", {})
    trace_store = TraceStore(str(trace_cfg.get("db_path", "~/.wikifs/traces.db")))
    router = create_default_router()
    collector = TraceCollector()
    interpreter = Interpreter(
        router,
        collector,
        handlers=handlers,
        trace_store=trace_store,
        error_collector=error_collector,
        run_store=run_store,
        path_rewriter=_path_rewriter_srv,
        supported_languages=handler_config.supported_languages,
    )
    return ServerContext(
        interpreter=interpreter,
        cache=cache,
        trace_store=trace_store,
        error_store=error_store,
        run_store=run_store,
    )


__all__ = [
    "ApiConfig",
    "Cache",
    "CacheConfig",
    "CacheStats",
    "Command",
    "CommandResponse",
    "ErrorCollector",
    "ErrorEntry",
    "ErrorStore",
    "Interpreter",
    "RouteMatch",
    "Router",
    "Run",
    "RunStore",
    "ServerContext",
    "Trace",
    "TraceCollector",
    "TracePhase",
    "TraceStats",
    "TraceStore",
    "create_default_router",
    "create_interpreter",
    "create_interpreter_with_components",
    "load_config",
    "normalize_path",
]
