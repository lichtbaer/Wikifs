# cat

Display file contents.

## Syntax

```bash
wikifs cat PATH
```

## Examples

### Read article (default language)

```bash
wikifs cat /wiki/entities/Frankfurt_am_Main/article.md
```

Returns the full Wikipedia article as Markdown. Default language is configured in `config.toml` (e.g. `de`).

### Read article in specific language

```bash
wikifs cat /wiki/entities/Frankfurt_am_Main/article.en.md
```

### Read summary

```bash
wikifs cat /wiki/entities/Frankfurt_am_Main/summary.md
```

Shorter extract of the article.

### Read property value

```bash
wikifs cat /wiki/entities/Frankfurt_am_Main/properties/population.txt
wikifs cat /wiki/entities/Frankfurt_am_Main/properties/p1082.txt
```

Property names can be human-readable (e.g. `population`) or Wikidata P-IDs (e.g. `p1082`).

### Read section

```bash
wikifs cat /wiki/entities/Frankfurt_am_Main/sections/Geography.md
```

### Read entity metadata

```bash
wikifs cat /wiki/entities/Frankfurt_am_Main/meta.json
```

Returns JSON with entity ID, labels, and metadata.

## Error Behavior

- **Not found (exit 2)**: Entity or file does not exist. May include suggestions.
- **Invalid path (exit 1)**: Path does not start with `/wiki/`.
