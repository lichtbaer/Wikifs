"""Command and response models for WikiFS interpreter."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Command:
    """Parsed command from JSON input."""

    command: str  # "ls", "cat", "grep", "search"
    path: str  # "/wiki/entities/Frankfurt_am_Main/properties/"
    flags: list[str]  # ["-l"], ["-i"], ["--type", "entity"]
    pattern: str | None  # For grep: search pattern
    request_id: str  # UUID v4, from client or generated


@dataclass
class CommandResponse:
    """Response from command execution."""

    output: str  # Terminal-like output
    exit_code: int  # 0 = success, 1 = error, 2 = not found
    request_id: str
    trace_id: str
    timing_ms: float
    error_type: str | None = None  # "entity_not_found", "invalid_command", etc.
    suggestions: list[str] | None = None  # For typos or ambiguities
