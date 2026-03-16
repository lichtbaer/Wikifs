# Architecture Decision Records

ADR (Architecture Decision Record) documents capture significant design decisions. WikiFS design decisions are documented in the project README and codebase.

## Key Decisions

| Topic | Decision |
|-------|----------|
| **Naming** | Wikipedia titles (underscores), Wikidata ID as symlink alias |
| **Multilingual** | `article.md` = default (configurable), `article.{lang}.md` for others |
| **Properties** | Flat structure, no grouping |
| **Rate limiting** | Delayed response, no error files |
| **No FUSE** | Command interpreter as core, not a real filesystem |
| **search vs grep** | `search` for cross-entity; `grep` for within-entity |
| **Traces** | SQLite-based, queryable, portable |
| **Sync-first** | No asyncio in PoC |

## References

- Project README — Overview and fixed design decisions
- [Architecture Overview](overview.md) — Data flow and layers
- [The Pattern](the-pattern.md) — Applying the pattern to other data sources
