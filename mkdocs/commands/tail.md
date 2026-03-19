# tail

Print the last *N* lines of a text-backed file (same paths as `cat`).

## Syntax

```bash
wikifs tail [-n LINES] PATH
```

Default is 10 lines if `-n` is omitted (CLI).

## Examples

```bash
wikifs tail -n 30 /wiki/entities/Berlin/article.md
```

## Flags

Same as [head](head.md): `-n` / `--lines`.
