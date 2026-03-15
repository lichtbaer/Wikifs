# What is WikiFS

WikiFS is a virtual filesystem over Wikipedia and Wikidata. It exposes Wikipedia articles and the Wikidata knowledge graph via familiar shell commands (`ls`, `cat`, `grep`, `search`). Under the hood: structured API calls and SPARQL queries.

## Concept

WikiFS is not a real filesystem (no FUSE). It is a **command interpreter** that accepts JSON commands, routes paths, calls backends, and returns terminal-like output. AI agents work with the interface they know — paths like `/wiki/entities/Frankfurt_am_Main/article.md` map to Wikipedia and Wikidata APIs.

```
Agent → JSON Command → Interpreter → Path Router → Backend Client → Response Formatter → Agent
```

Each run produces a trace (SQLite-based) for performance analysis and learning.

## Key Features

- **Read-only commands**: `ls`, `cat`, `grep`, `search`
- **Entity navigation**: Browse entities by Wikipedia title or Wikidata ID
- **Properties and relations**: Access Wikidata properties and follow relations
- **Articles as Markdown**: Wikipedia content in Markdown format
- **Two-level cache**: In-memory LRU + SQLite for faster repeated access
- **Tracing**: SQLite-based traces for performance analysis

## Quick Example

```bash
wikifs ls /wiki/entities/Frankfurt_am_Main/
wikifs cat /wiki/entities/Frankfurt_am_Main/article.md
wikifs search "Goethe" --type entity --limit 5
```

See [Getting Started](getting-started.md) to run your first command in under 5 minutes.
