"""Tests for FastAPI HTTP server."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app


@pytest.fixture
def temp_config(tmp_path: Path) -> Path:
    """Create temp config with temp dirs for cache and traces."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[cache]
l2_db_path = "{tmp_path / "cache.db"}"

[tracing]
db_path = "{tmp_path / "traces.db"}"
"""
    )
    return config_path


def test_health_returns_ok_and_version() -> None:
    """GET /health returns status and version."""
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert data["version"] == "0.1.0"


def test_execute_valid_command_returns_command_response(temp_config: Path) -> None:
    """POST /execute with valid command returns CommandResponse as JSON."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.post(
            "/execute",
            json={
                "command": "ls",
                "path": "/wiki/entities/Frankfurt_am_Main/",
                "flags": [],
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert "output" in data
    assert "exit_code" in data
    assert data["exit_code"] == 0
    assert "request_id" in data
    assert "trace_id" in data
    assert "timing_ms" in data
    assert "article.md" in data["output"] or "handler=" in data["output"]


def test_execute_include_trace_returns_full_trace(temp_config: Path) -> None:
    """POST /execute?include_trace=true returns full trace object."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.post(
            "/execute",
            params={"include_trace": "true"},
            json={
                "command": "ls",
                "path": "/wiki/entities/Frankfurt_am_Main/",
                "flags": [],
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert "trace" in data
    trace = data["trace"]
    assert "phases" in trace
    assert "cache_hits" in trace
    assert "api_calls" in trace
    assert trace["trace_id"] == data["trace_id"]


def test_execute_invalid_command_returns_200_with_exit_code_1() -> None:
    """Invalid commands return HTTP 200 with exit_code 1 (interpreter handles it)."""
    with TestClient(app) as c:
        r = c.post(
            "/execute",
            json={
                "command": "rm",
                "path": "/wiki/entities/Frankfurt/",
                "flags": [],
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["exit_code"] == 1
    assert data["error_type"] == "invalid_command"


def test_stats_returns_trace_aggregate(temp_config: Path) -> None:
    """GET /stats returns TraceStats as JSON."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.get("/stats")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "avg_duration_ms" in data
    assert "p50_duration_ms" in data
    assert "p95_duration_ms" in data
    assert "max_duration_ms" in data
    assert "cache_hit_rate" in data
    assert "commands_by_type" in data


def test_traces_slow_filter(temp_config: Path) -> None:
    """GET /traces?slow=500 filters by min duration."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.get("/traces", params={"slow": 500})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    for t in data:
        assert t["total_duration_ms"] >= 500


def test_cache_clear_returns_deleted_count(temp_config: Path) -> None:
    """DELETE /cache clears cache and returns deleted count."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.delete("/cache")
    assert r.status_code == 200
    data = r.json()
    assert "deleted" in data
    assert isinstance(data["deleted"], int)


def test_agent_returns_answer_and_commands_executed(monkeypatch: pytest.MonkeyPatch) -> None:
    """POST /agent returns answer, commands_executed, total_commands, total_duration_ms."""
    from wikifs.agent_models import AgentResponse, CommandExecuted

    mock_response = AgentResponse(
        answer="Frankfurt has about 750,000 inhabitants.",
        commands_executed=[
            CommandExecuted(
                command="search",
                path="/wiki/search (query='Frankfurt')",
                timing_ms=120.0,
            ),
            CommandExecuted(
                command="cat",
                path="/wiki/entities/Frankfurt_am_Main/properties/population.txt",
                timing_ms=85.0,
            ),
        ],
        total_commands=2,
        total_duration_ms=1500.0,
    )

    def mock_run_agent(
        query: str,
        config_path: str | None = None,
        model: str | None = None,
    ) -> AgentResponse:
        return mock_response

    monkeypatch.setattr("wikifs.agent.run_agent", mock_run_agent)

    with TestClient(app) as c:
        r = c.post("/agent", json={"query": "What is the population of Frankfurt?"})
    assert r.status_code == 200
    data = r.json()
    assert data["answer"] == "Frankfurt has about 750,000 inhabitants."
    assert data["total_commands"] == 2
    assert data["total_duration_ms"] == 1500.0
    assert len(data["commands_executed"]) == 2
    assert data["commands_executed"][0]["command"] == "search"
    assert data["commands_executed"][0]["path"] == "/wiki/search (query='Frankfurt')"
    assert data["commands_executed"][0]["timing_ms"] == 120.0


def test_agent_invalid_request_returns_400() -> None:
    """POST /agent with missing query returns 400 or 422."""
    with TestClient(app) as c:
        r = c.post("/agent", json={})
    assert r.status_code in (400, 422)  # Validation error


def test_cors_allows_localhost() -> None:
    """CORS allows requests from localhost origins."""
    with TestClient(app) as c:
        r = c.options(
            "/execute",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
            },
        )
    # FastAPI/Starlette CORS middleware responds to preflight
    assert r.status_code in (200, 204)
    # Allow-Origin should be present for matching origin
    assert "access-control-allow-origin" in [
        h.lower() for h in r.headers.keys()
    ] or "http://localhost:5173" in str(r.headers.get("Access-Control-Allow-Origin", ""))
