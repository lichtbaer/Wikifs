# ls

List directory contents.

## Syntax

```bash
wikifs ls PATH [-l]
```

## Flags

| Flag | Description |
|------|-------------|
| `-l` | Long listing format |

## Examples

### List entity directory

```bash
wikifs ls /wiki/entities/Frankfurt_am_Main/
```

Output:

```
article.md
summary.md
properties/
relations/
sections/
meta.json
```

### Long format

```bash
wikifs ls -l /wiki/entities/Frankfurt_am_Main/
```

Shows additional metadata (e.g. type, size hints).

### List relations

```bash
wikifs ls /wiki/entities/Frankfurt_am_Main/relations/
```

Output (excerpt):

```
part_of/
located_in/
country/
...
```

### List relation targets

```bash
wikifs ls /wiki/entities/Frankfurt_am_Main/relations/part_of/
```

Output (excerpt):

```
Hessen
Deutschland
```

### List classes

```bash
wikifs ls /wiki/classes/
wikifs ls /wiki/classes/city/
```

## Error Behavior

- **Not found (exit 2)**: Unknown entity or invalid path. May include suggestions for similar entities.
- **Invalid path (exit 1)**: Path does not start with `/wiki/`.
