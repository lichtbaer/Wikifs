"""Pydantic models for WikiFS Agent I/O."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    """Request body for POST /agent."""

    query: str = Field(..., description="Natural language question for the agent")
    model: str | None = Field(
        default=None,
        description="Optional model override (e.g. openai:gpt-4o, anthropic:claude-sonnet)",
    )


class CommandExecuted(BaseModel):
    """Single command executed by the agent."""

    command: str = Field(..., description="Command name (ls, cat, grep, search)")
    path: str = Field(..., description="Path or context used")
    timing_ms: float = Field(..., description="Execution time in milliseconds")
    trace_id: str | None = Field(
        default=None,
        description="Trace ID from interpreter execution",
    )
    exit_code: int = Field(
        default=0,
        description="Exit code from command execution",
    )


class AgentResponse(BaseModel):
    """Response from POST /agent."""

    answer: str = Field(..., description="Agent's answer to the query")
    commands_executed: list[CommandExecuted] = Field(
        default_factory=list,
        description="List of WikiFS commands executed",
    )
    total_commands: int = Field(..., description="Total number of commands executed")
    total_duration_ms: float = Field(..., description="Total agent run duration in ms")
