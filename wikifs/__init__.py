"""WikiFS — Virtual Filesystem over Wikipedia & Wikidata."""

__version__ = "0.1.0"

from wikifs.tracing import (
    Trace,
    TraceCollector,
    TracePhase,
    TraceStats,
    TraceStore,
)

__all__ = [
    "Trace",
    "TraceCollector",
    "TracePhase",
    "TraceStats",
    "TraceStore",
]
