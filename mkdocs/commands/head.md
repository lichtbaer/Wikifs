# head

Print the first *N* lines of a text-backed file (same paths as `cat`). Useful for long articles.

## Syntax

```bash
wikifs head [-n LINES] PATH
```

Default is 10 lines if `-n` is omitted (CLI). The JSON API sends `-n` explicitly or relies on the default of 10.

## Examples

```bash
wikifs head -n 50 /wiki/entities/Berlin/article.md
wikifs head /wiki/entities/Berlin/summary.md
```

## Flags (API / interpreter)

| Flag | Meaning |
|------|---------|
| `-n`, `--lines` | Number of lines (0–100000; last wins if repeated) |

Supported for the same routes as `cat` where output is line-oriented text (articles, summaries, sections, properties, `meta.json`, `_all.json`, and search/SPARQL results when using `search`/`cat`/`head`/`tail` on `/wiki/search` or SPARQL paths).
