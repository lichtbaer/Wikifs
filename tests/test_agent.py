"""Tests for WikiFS agent."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from wikifs.agent import AgentDeps, create_wikifs_agent, run_agent
from wikifs.agent_models import AgentResponse, CommandExecuted


def test_agent_deps_has_interpreter_and_commands() -> None:
    """AgentDeps contains interpreter and commands_executed list."""
    from wikifs import create_interpreter

    interpreter = create_interpreter()
    deps = AgentDeps(interpreter=interpreter)
    assert deps.interpreter is interpreter
    assert deps.commands_executed == []


def test_create_wikifs_agent_returns_agent_and_deps() -> None:
    """create_wikifs_agent returns (agent, deps) tuple."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "config.toml"
        config_path.write_text(
            f"""
[cache]
l2_db_path = "{tmp}/cache.db"

[tracing]
db_path = "{tmp}/traces.db"

[agent]
default_model = "openai:gpt-4o"
max_tool_calls = 5
"""
        )
        agent, deps = create_wikifs_agent(config_path=str(config_path))
    assert agent is not None
    assert deps is not None
    assert deps.interpreter is not None


def test_agent_models_agent_response() -> None:
    """AgentResponse serializes correctly."""
    resp = AgentResponse(
        answer="Test answer",
        commands_executed=[
            CommandExecuted(command="ls", path="/wiki/entities/Berlin", timing_ms=100.0),
        ],
        total_commands=1,
        total_duration_ms=500.0,
    )
    data = resp.model_dump()
    assert data["answer"] == "Test answer"
    assert data["total_commands"] == 1
    assert data["total_duration_ms"] == 500.0
    assert len(data["commands_executed"]) == 1
    assert data["commands_executed"][0]["command"] == "ls"
    assert data["commands_executed"][0]["path"] == "/wiki/entities/Berlin"
    assert data["commands_executed"][0]["timing_ms"] == 100.0


@pytest.mark.skipif(
    not __import__("os").environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY not set",
)
def test_run_agent_integration() -> None:
    """Run agent with real API (requires OPENAI_API_KEY)."""
    with tempfile.TemporaryDirectory() as tmp:
        config_path = Path(tmp) / "config.toml"
        config_path.write_text(
            f"""
[cache]
l2_db_path = "{tmp}/cache.db"

[tracing]
db_path = "{tmp}/traces.db"

[agent]
default_model = "openai:gpt-4o"
max_tool_calls = 10
"""
        )
        result = run_agent(
            "What is the population of Frankfurt?",
            config_path=str(config_path),
        )
    assert isinstance(result, AgentResponse)
    assert result.answer
    assert result.total_commands >= 2  # Agent should use at least 2 commands
    assert result.commands_executed
    assert result.total_duration_ms > 0
