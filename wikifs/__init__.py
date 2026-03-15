"""WikiFS — Virtual Filesystem over Wikipedia & Wikidata."""

__version__ = "0.1.0"

from wikifs.cache import Cache, CacheConfig, CacheStats
from wikifs.config import ApiConfig, load_config
from wikifs.handlers import create_handler_config, create_handlers
from wikifs.interpreter import Interpreter
from wikifs.models import Command, CommandResponse
from wikifs.router import RouteMatch, Router, create_default_router, normalize_path
from wikifs.tracing import (
    Trace,
    TraceCollector,
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
    cache_cfg = config.get("cache", {})
    cache = Cache(
        CacheConfig(
            l1_max_size=int(cache_cfg.get("l1_max_size", 256)),
            l1_ttl_seconds=int(cache_cfg.get("l1_ttl_seconds", 3600)),
            l2_ttl_seconds=int(cache_cfg.get("l2_ttl_seconds", 86400)),
            l2_db_path=str(cache_cfg.get("l2_db_path", "~/.wikifs/cache.db")),
        )
    )
    handler_config = create_handler_config(config)
    handlers = create_handlers(api_config, cache, handler_config)
    trace_cfg = config.get("tracing", {})
    trace_store = TraceStore(str(trace_cfg.get("db_path", "~/.wikifs/traces.db")))
    router = create_default_router()
    collector = TraceCollector()
    return Interpreter(
        router, collector, handlers=handlers, trace_store=trace_store
    )


__all__ = [
    "ApiConfig",
    "Cache",
    "CacheConfig",
    "CacheStats",
    "Command",
    "CommandResponse",
    "Interpreter",
    "RouteMatch",
    "Router",
    "Trace",
    "TraceCollector",
    "TracePhase",
    "TraceStats",
    "TraceStore",
    "create_default_router",
    "create_interpreter",
    "load_config",
    "normalize_path",
]
