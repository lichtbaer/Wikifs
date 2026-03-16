# search

Search across entities or run SPARQL queries.

## Syntax

```bash
wikifs search "QUERY" [--type entity] [--limit N]
wikifs search --sparql "SPARQL_QUERY"
```

## Flags

| Flag | Description |
|------|-------------|
| `--type` | Search type (default: `entity`) |
| `--limit` | Maximum number of results |
| `--sparql` | Run raw SPARQL query instead of entity search |

## Examples

### Entity search

```bash
wikifs search "Goethe" --type entity --limit 5
```

Output: Matching entities with labels and IDs.

### Entity search (default limit)

```bash
wikifs search "Frankfurt"
```

Uses default limit from config (e.g. 100).

### SPARQL query

```bash
wikifs search --sparql "SELECT ?x WHERE { ?x wdt:P31 wd:Q515 } LIMIT 5"
```

Returns CSV-formatted result. Path is implicitly `/wiki/sparql/result.csv`.

### Find cities (SPARQL)

```bash
wikifs search --sparql "SELECT ?city ?cityLabel WHERE { ?city wdt:P31 wd:Q515 . SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". } } LIMIT 10"
```

## Error Behavior

- **Invalid --limit (exit 1)**: Value must be a valid integer.
- **Unknown flag (exit 1)**: Only `--type`, `--limit`, and `--sparql` are allowed.
- **Not found (exit 2)**: No results or query error.
