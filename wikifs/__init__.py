"""WikiFS — Virtual Filesystem over Wikipedia & Wikidata."""

__version__ = "0.1.0"

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

__all__ = [
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
    "normalize_path",
]
