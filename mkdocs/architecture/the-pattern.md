# The Pattern: Filesystem as Integration Layer

WikiFS demonstrates the pattern **"Filesystem as Integration Layer"**: arbitrary structured data sources exposed via a POSIX-like abstraction for AI agents.

## Idea

AI agents are trained on shell commands. They understand `ls`, `cat`, `grep`. Instead of teaching them custom APIs, expose your data as a virtual filesystem. Agents navigate paths, read files, and search — using the interface they already know.

## Components to Adapt

When applying this pattern to your own data source:

1. **Path schema** — Define a hierarchy that maps to your domain. Example: `/wiki/entities/{id}/`, `/wiki/entities/{id}/properties/`.
2. **Router** — Regex-based path matching to handler names. Use `{param}` for capture groups.
3. **Handlers** — One handler per route. Handlers receive `command`, `params`, `flags`, `pattern`. They call your backend and return terminal-like output.
4. **Formatter** — Convert backend responses to plain text or Markdown. Agents consume text, not raw JSON.
5. **Cache** — Optional. LRU + persistent cache reduces latency for repeated access.
6. **Tracing** — Optional. Helps debug slow paths and optimize.

## Data Flow (Generic)

```
Agent → Command (ls/cat/grep/search) + Path
     → Router matches path → Handler
     → Handler calls Backend (your API, DB, etc.)
     → Formatter produces terminal output
     → Agent receives text
```

## Design Choices in WikiFS

| Choice | Rationale |
|--------|-----------|
| No FUSE | Command interpreter is simpler, portable, works in containers |
| Sync-first | No asyncio in PoC; easier to reason about |
| JSON input | HTTP API and CLI both send same structure |
| Trailing slash optional | Paths normalized; `/wiki/entities/X` and `/wiki/entities/X/` both work |
| `search` vs cross-entity grep | Honest interface: grep is local, search is global |
| Properties flat | No grouping; each property = one file |
| Rate limiting as delayed response | No error files; agent gets data eventually |

## Applying to Your Data

1. Define paths that make sense for your domain (e.g. `/data/customers/{id}/orders/`).
2. Implement handlers that fetch from your APIs or databases.
3. Format responses as plain text or Markdown.
4. Register routes in the router.
5. Add caching if your backend is slow or rate-limited.

See [ADRs](adrs.md) for more design decisions.
