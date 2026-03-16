# Observability

WikiFS provides stats and trace commands for performance analysis.

## stats

Aggregate statistics from all recorded traces.

```bash
wikifs stats
```

Output:

```
Total Commands:    42
Avg Duration:      156.3 ms
P50 Duration:      120.0 ms
P95 Duration:      450.0 ms
Max Duration:      890.0 ms
Cache Hit Rate:    65.2%
Commands by Type:
  ls: 15
  cat: 18
  grep: 3
  search: 6
```

## traces

Query trace data with filters.

```bash
wikifs traces [--slow MS] [--path PATTERN] [--command CMD] [--limit N]
```

| Option | Description |
|--------|-------------|
| `--slow` | Show traces slower than N milliseconds |
| `--path` | Filter by path (SQL LIKE pattern) |
| `--command` | Filter by command type |
| `--limit` | Max traces to show (default: 50) |

### Examples

```bash
# Traces slower than 500 ms
wikifs traces --slow 500

# Traces for article reads
wikifs traces --path "/wiki/entities/*/article.md"

# Traces for cat commands
wikifs traces --command cat

# Combine filters
wikifs traces --slow 300 --command search --limit 20
```

### traces clear

Delete old traces (housekeeping).

```bash
wikifs traces clear [--older-than N]
```

| Option | Description |
|--------|-------------|
| `--older-than` | Delete traces older than N days. Use `0` to delete all. |

Example:

```bash
wikifs traces clear --older-than 7
```

## cache stats

Cache hit/miss statistics.

```bash
wikifs cache stats
```

Output:

```
L1 Hits:     45
L1 Misses:   12
L2 Hits:     8
L2 Misses:   4
Hit Rate:    80.3%
L1 Size:     57
L2 Size:     12
Total Reqs:  69
```

## cache clear

Clear both cache levels.

```bash
wikifs cache clear
```

Output: `Cleared N cache entry(ies).`

## errors

Query or export recorded errors (API failures, agent errors, etc.). Errors are stored when the server or agent records them; the database path is configured under `[errors]` in config (default: `~/.wikifs/errors.db`).

```bash
wikifs errors [--since TIME] [--category CAT] [--unresolved] [--run-id ID] [--format json|text] [--limit N]
```

| Option | Description |
|--------|-------------|
| `--since` | Filter by time (e.g. `24h`, `7d`) |
| `--category` | Filter by category (api, cache, parsing, routing, agent, timeout) |
| `--unresolved` | Show only unresolved errors |
| `--run-id` | Filter by run ID |
| `--format` | Output format: `text` (default) or `json` |
| `--limit` | Max errors to show (default: 100) |

### errors summary

Aggregate errors by category and severity.

```bash
wikifs errors summary
```

For the HTTP API equivalents, see [API Reference](api.md#get-errors) (GET /errors, GET /errors/summary, PATCH /errors/{error_id}).

## runs

Query runs (CLI and agent executions). Run data is stored in the same database as errors.

```bash
wikifs runs [--failed] [--type cli|agent] [--since TIME] [--format json|text] [--limit N]
wikifs runs --id RUN_ID [--full] [--format json|text]
```

| Option | Description |
|--------|-------------|
| `--failed` | Show only failed runs |
| `--type` | Filter by type: `cli` or `agent` |
| `--since` | Filter by time (e.g. `24h`, `7d`) |
| `--format` | Output format: `text` (default) or `json` |
| `--limit` | Max runs to show (default: 50) |
| `--id` | Show a single run by ID |
| `--full` | With `--id`: include traces and errors for that run |

For the HTTP API, see [API Reference](api.md#get-runs) (GET /runs, GET /runs/{run_id}).
