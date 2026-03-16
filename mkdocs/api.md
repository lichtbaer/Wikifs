# HTTP API Reference

The WikiFS HTTP API is a thin wrapper around the interpreter. Start the server with `wikifs serve --port 8000`.

## Base URL

`http://localhost:8000` (default)

## Endpoints

### GET /health

Health check.

**Response:**

```json
{"status": "ok", "version": "0.1.0"}
```

### POST /execute

Execute a command.

**Request body:**

```json
{
  "command": "ls",
  "path": "/wiki/entities/Frankfurt_am_Main/",
  "flags": [],
  "pattern": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `command` | string | yes | `ls`, `cat`, `grep`, or `search` |
| `path` | string | yes | Path (must start with `/wiki/`) |
| `flags` | array | no | e.g. `["-l"]`, `["--limit", "5"]` |
| `pattern` | string | no | For grep: search pattern. For search: query string. |
| `request_id` | string | no | Client-provided ID (UUID) |

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `include_trace` | bool | false | Include full trace in response |

**Response:**

```json
{
  "output": "article.md\nsummary.md\nproperties/\n...",
  "exit_code": 0,
  "request_id": "uuid",
  "trace_id": "uuid",
  "timing_ms": 45.2,
  "error_type": null,
  "suggestions": null
}
```

With `?include_trace=true`, adds `trace` object with phases, durations, cache hits.

### GET /stats

Aggregate trace statistics.

**Response:**

```json
{
  "count": 42,
  "avg_duration_ms": 156.3,
  "p50_duration_ms": 120.0,
  "p95_duration_ms": 450.0,
  "max_duration_ms": 890.0,
  "cache_hit_rate": 0.652,
  "commands_by_type": {"ls": 15, "cat": 18, "grep": 3, "search": 6}
}
```

### GET /traces

Query traces.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `slow` | float | - | Min duration (ms) |
| `command` | string | - | Filter by command |
| `path` | string | - | Filter by path (SQL LIKE) |
| `limit` | int | 50 | Max results |

**Response:** Array of trace objects.

### DELETE /cache

Clear cache.

**Response:**

```json
{"deleted": 42}
```

### POST /agent

Run the WikiFS AI agent on a natural-language query (non-streaming).

**Request body:**

```json
{
  "query": "Wie viele Einwohner hat Berlin?",
  "model": null
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | yes | Natural-language question |
| `model` | string | no | Model override (e.g. `openai:gpt-4o`, `anthropic:claude-sonnet-4-20250514`) |

**Response:**

```json
{
  "answer": "Berlin hat etwa 3,7 Millionen Einwohner...",
  "commands_executed": [
    {"command": "ls", "path": "/wiki/entities/Berlin/", "timing_ms": 120.5, "trace_id": "uuid", "exit_code": 0},
    {"command": "cat", "path": "/wiki/entities/Berlin/properties/population.txt", "timing_ms": 85.2, "trace_id": "uuid", "exit_code": 0}
  ],
  "total_commands": 2,
  "total_duration_ms": 450.3
}
```

On missing API key or agent error, returns 400 with detail message.

### POST /agent/stream

Run the agent with Server-Sent Events (streaming). Same request body as POST /agent.

**Response:** `text/event-stream` with events:

| Event | Description |
|-------|-------------|
| `agent_start` | Run started; data: `run_id`, `query`, `model` |
| `thinking` | Agent is planning; data: `message` |
| `tool_call` | A WikiFS command is being run; data: `command`, `path`, `pattern` (optional), `step` |
| `tool_result` | Command finished; data: `step`, `output`, `exit_code`, `timing_ms`, `trace` (optional) |
| `answer` | Final answer; data: `answer`, `total_commands`, `total_duration_ms`, `cache_hits` |
| `error` | Agent or tool error; data: `message`, `step`, `category` |
| `done` | Stream ended; data: `run_id`, `success` |

### GET /errors

Query recorded errors.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `since` | string | - | Filter by time (e.g. ISO timestamp) |
| `category` | string | - | Filter by category (api, cache, parsing, routing, agent, timeout) |
| `severity` | string | - | Filter by severity |
| `run_id` | string | - | Filter by run ID |
| `unresolved` | bool | false | Only unresolved errors |
| `limit` | int | 100 | Max results |

**Response:** Array of error objects (`error_id`, `timestamp`, `trace_id`, `run_id`, `category`, `severity`, `command`, `path`, `message`, `details`, `resolved`).

### GET /errors/summary

Aggregate errors by category and severity.

**Response:** Object mapping category → severity → count, e.g. `{"agent": {"error": 2}, "api": {"warning": 1}}`.

### PATCH /errors/{error_id}

Mark an error as resolved.

**Response:** `{"error_id": "...", "resolved": true}`. Returns 404 if error not found.

### GET /runs

Query runs (CLI and agent executions).

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `failed` | bool | false | Only failed runs |
| `type` | string | - | Filter by type (e.g. `cli`, `agent`) |
| `since` | string | - | Filter by time |
| `limit` | int | 50 | Max results |

**Response:** Array of run objects (`run_id`, `timestamp`, `type`, `query`, `trace_ids`, `error_ids`, `duration_ms`, `success`, `result`, `model`, `commands_count`).

### GET /runs/{run_id}

Get a single run. Add `?full=true` to include `traces` and `errors` arrays (trace/error summaries for that run).

**Response (without full):** Run object with `run_id`, `timestamp`, `type`, `query`, `trace_ids`, `error_ids`, `duration_ms`, `success`, `result`, `model`, `commands_count`.

**Response (with full=true):** Same plus `traces` (list of `trace_id`, `command`, `path`, `timing_ms`, `exit_code`) and `errors` (list of `error_id`, `category`, `severity`, `message`, `details`). Returns 404 if run not found.

## CORS

CORS is enabled for `http://localhost:*` and `http://127.0.0.1:*` to allow the Explorer UI.
