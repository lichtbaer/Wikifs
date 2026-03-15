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

## CORS

CORS is enabled for `http://localhost:*` and `http://127.0.0.1:*` to allow the Explorer UI.
