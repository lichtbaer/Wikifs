# grep

Search within files. Matches text in a single entity's files.

## Syntax

```bash
wikifs grep PATTERN PATH [-i] [-c]
```

## Flags

| Flag | Description |
|------|-------------|
| `-i` | Ignore case |
| `-c` | Count matches only |

## Examples

### Basic grep

```bash
wikifs grep "Goethe" /wiki/entities/Frankfurt_am_Main/article.md
```

Output: Lines containing "Goethe" with context.

### Ignore case

```bash
wikifs grep -i "goethe" /wiki/entities/Frankfurt_am_Main/
```

Searches within the entity directory (typically article and summary). Case-insensitive.

### Count matches

```bash
wikifs grep -i -c "frankfurt" /wiki/entities/Frankfurt_am_Main/summary.md
```

Output: Number of matching lines.

### Combined flags

```bash
wikifs grep -i -c "main" /wiki/entities/Frankfurt_am_Main/article.md
```

## Scope

`grep` operates on a single entity or file. For cross-entity search, use [search](search.md).

## Error Behavior

- **Cross-entity grep (exit 1)**: Using `grep` on `/wiki/entities/` (no specific entity) returns "Use `search` for cross-entity queries".
- **Not found (exit 2)**: Entity or path does not exist.
- **Unknown flag (exit 1)**: Only `-i` and `-c` are allowed.
