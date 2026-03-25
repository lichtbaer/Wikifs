"""Tests for FastAPI HTTP server."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server import app


@pytest.fixture
def temp_config(tmp_path: Path) -> Path:
    """Create temp config with temp dirs for cache, traces, and errors."""
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        f"""
[cache]
l2_db_path = "{tmp_path / "cache.db"}"

[tracing]
db_path = "{tmp_path / "traces.db"}"

[errors]
db_path = "{tmp_path / "errors.db"}"
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


def test_health_ok_without_key_when_wikifs_api_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /health stays public when WIKIFS_API_KEY is configured."""
    monkeypatch.setenv("WIKIFS_API_KEY", "secret-for-tests")
    with TestClient(app) as c:
        r = c.get("/health")
    assert r.status_code == 200


def test_execute_returns_401_without_key_when_wikifs_api_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """POST /execute requires API key when WIKIFS_API_KEY is set."""
    monkeypatch.setenv("WIKIFS_API_KEY", "secret-for-tests")
    with TestClient(app) as c:
        r = c.post(
            "/execute",
            json={"command": "ls", "path": "/wiki/classes/", "flags": []},
        )
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid or missing API key"


def test_execute_with_x_api_key_succeeds(
    monkeypatch: pytest.MonkeyPatch, temp_config: Path
) -> None:
    """Valid X-API-Key header allows access when WIKIFS_API_KEY is set."""
    monkeypatch.setenv("WIKIFS_API_KEY", "secret-for-tests")
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.post(
            "/execute",
            headers={"X-API-Key": "secret-for-tests"},
            json={
                "command": "ls",
                "path": "/wiki/entities/Frankfurt_am_Main/",
                "flags": [],
            },
        )
    assert r.status_code == 200
    assert r.json()["exit_code"] == 0


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


def test_agent_stream_returns_sse_events(
    monkeypatch: pytest.MonkeyPatch, temp_config: Path
) -> None:
    """POST /agent/stream returns Server-Sent Events stream."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    def mock_run_agent_streaming(
        query: str,
        callback: object,
        config_path: str | None = None,
        model: str | None = None,
        trace_store: object = None,
    ) -> object:
        from wikifs.agent import AgentEvent

        cb = callback
        if callable(cb):
            cb(
                AgentEvent(
                    "agent_start",
                    {"run_id": "test-123", "query": query, "model": "openai:gpt-4o"},
                )
            )
            cb(AgentEvent("thinking", {"message": "Planning..."}))
            cb(
                AgentEvent(
                    "tool_call",
                    {
                        "command": "search",
                        "path": "/wiki/search",
                        "pattern": "Berlin",
                        "step": 1,
                    },
                )
            )
            cb(
                AgentEvent(
                    "tool_result",
                    {
                        "step": 1,
                        "output": "Berlin Q64",
                        "exit_code": 0,
                        "timing_ms": 50,
                        "trace": None,
                    },
                )
            )
            cb(
                AgentEvent(
                    "answer",
                    {
                        "answer": "Berlin has 3.7M inhabitants.",
                        "total_commands": 1,
                        "total_duration_ms": 200,
                    },
                )
            )
            cb(AgentEvent("done", {"run_id": "test-123", "success": True}))
        from wikifs.agent_models import AgentResponse, CommandExecuted

        return AgentResponse(
            answer="Berlin has 3.7M inhabitants.",
            commands_executed=[
                CommandExecuted(command="search", path="/wiki/search", timing_ms=50.0),
            ],
            total_commands=1,
            total_duration_ms=200.0,
        )

    monkeypatch.setattr("server.run_agent_streaming", mock_run_agent_streaming)

    with TestClient(app) as c:
        r = c.post("/agent/stream", json={"query": "Population of Berlin?"})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers.get("content-type", "")
    text = r.text
    assert "event: agent_start" in text
    assert "event: thinking" in text
    assert "event: tool_call" in text
    assert "event: tool_result" in text
    assert "event: answer" in text
    assert "event: done" in text
    assert "run_id" in text
    assert "Berlin" in text


def test_errors_endpoint(temp_config: Path) -> None:
    """GET /errors returns error list (possibly empty)."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.get("/errors")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_errors_summary_endpoint(temp_config: Path) -> None:
    """GET /errors/summary returns aggregation."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.get("/errors/summary")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_runs_endpoint(temp_config: Path) -> None:
    """GET /runs returns run list (possibly empty)."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.get("/runs")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_execute_creates_run(temp_config: Path) -> None:
    """POST /execute creates a run in RunStore."""
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
    runs = server_module._server_ctx.run_store.query(limit=10)
    assert len(runs) >= 1
    assert runs[0].type == "cli"
    assert runs[0].commands_count == 1


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


def test_complete_wiki_root_prefix(temp_config: Path) -> None:
    """POST /complete suggests top-level /wiki/ segments."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.post("/complete", json={"path": "/wiki/cla"})
    assert r.status_code == 200
    data = r.json()
    assert "/wiki/classes/" in data["candidates"]
    assert "error" not in data


def test_complete_invalid_prefix_returns_error() -> None:
    """POST /complete with non-wiki path returns error field."""
    with TestClient(app) as c:
        r = c.post("/complete", json={"path": "/etc/passwd"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("error")
    assert data["candidates"] == []


def test_execute_batch_runs_multiple_commands(temp_config: Path) -> None:
    """POST /execute/batch returns one result per command."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.post(
            "/execute/batch",
            json={
                "commands": [
                    {
                        "command": "ls",
                        "path": "/wiki/classes/",
                        "flags": [],
                    },
                    {
                        "command": "ls",
                        "path": "/wiki/classes/",
                        "flags": [],
                    },
                ]
            },
        )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 2
    assert len(data["results"]) == 2
    assert "total_timing_ms" in data
    assert all(x["exit_code"] == 0 for x in data["results"])


def test_execute_batch_applies_top_level_lang(temp_config: Path) -> None:
    """Optional body.lang is merged into batch items without their own lang."""
    import server as server_module

    server_module._server_ctx = None
    from wikifs import create_interpreter_with_components

    server_module._server_ctx = create_interpreter_with_components(str(temp_config))

    with TestClient(app) as c:
        r = c.post(
            "/execute/batch",
            json={
                "lang": "de",
                "commands": [
                    {
                        "command": "ls",
                        "path": "/wiki/entities/Frankfurt_am_Main/",
                        "flags": [],
                    },
                ],
            },
        )
    assert r.status_code == 200
    assert r.json()["results"][0]["exit_code"] == 0


def test_execute_batch_rejects_non_list_commands() -> None:
    """POST /execute/batch returns 422 when commands is not an array."""
    with TestClient(app) as c:
        r = c.post("/execute/batch", json={"commands": "ls"})
    assert r.status_code == 422


def test_execute_batch_rejects_oversized_batch() -> None:
    """POST /execute/batch returns 422 when too many commands."""
    with TestClient(app) as c:
        r = c.post(
            "/execute/batch",
            json={
                "commands": [
                    {"command": "ls", "path": "/wiki/classes/", "flags": []}
                ]
                * 51
            },
        )
    assert r.status_code == 422
