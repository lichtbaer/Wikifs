# Command Reference

WikiFS provides four read-only commands that mirror familiar shell operations.

| Command | Description |
|---------|-------------|
| [ls](ls.md) | List directory contents |
| [cat](cat.md) | Display file contents |
| [grep](grep.md) | Search within files |
| [search](search.md) | Search across entities or run SPARQL |

All commands use paths under `/wiki/`. Paths must start with `/wiki/`.

## Path Structure

- `/wiki/entities/{name}/` — Entity directory (Wikipedia title or Wikidata ID)
- `/wiki/entities/{name}/article.md` — Full Wikipedia article (Markdown)
- `/wiki/entities/{name}/summary.md` — Article summary
- `/wiki/entities/{name}/properties/` — Wikidata properties
- `/wiki/entities/{name}/properties/{prop}.txt` — Single property value
- `/wiki/entities/{name}/relations/` — Relation types
- `/wiki/entities/{name}/relations/{relation}/` — Relation targets
- `/wiki/entities/{name}/sections/` — Article sections
- `/wiki/classes/` — Entity classes (e.g. city, country)
- `/wiki/search` — Entity search
- `/wiki/sparql/result.csv` — SPARQL query result

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (invalid command, invalid path, etc.) |
| 2 | Not found |
