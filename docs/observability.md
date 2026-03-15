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
