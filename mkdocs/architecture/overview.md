# Architecture Overview

## Data Flow

```
┌─────────┐     JSON      ┌─────────────┐     path      ┌─────────────┐
│  Agent  │ ────────────► │ Interpreter │ ────────────► │ Path Router │
└─────────┘   command     └─────────────┘   normalized  └──────┬──────┘
     ▲                            │                           │
     │                            │ route match               │ handler
     │                            ▼                           ▼
     │                    ┌─────────────┐              ┌─────────────┐
     │                    │   Handler   │ ◄─────────────│  Backend    │
     │                    │ (entity,    │   API/SPARQL  │  Client     │
     │                    │  article,   │              │ (Wikipedia, │
     │                    │  search…)   │              │  Wikidata)  │
     │                    └──────┬──────┘              └─────────────┘
     │                           │                            │
     │                           │ formatted output           │
     │                           ▼                            │
     │                    ┌─────────────┐                     │
     └────────────────────│  Response   │                     │
            output        │  Formatter  │                     │
                          └──────┬──────┘                     │
                                 │                            │
                                 ▼                            ▼
                          ┌─────────────┐              ┌─────────────┐
                          │    Cache    │              │ Trace Store │
                          │ L1 (LRU) +  │              │  (SQLite)   │
                          │ L2 (SQLite) │              └─────────────┘
                          └─────────────┘
```

## Layers

| Layer | Responsibility |
|-------|----------------|
| **Interpreter** | Parse JSON command, validate command/path/flags, orchestrate execution |
| **Path Router** | Match path to handler via regex patterns |
| **Handlers** | Execute command for a route (entity list, article, properties, search) |
| **Backend Clients** | Call Wikipedia REST API and Wikidata SPARQL/API |
| **Cache** | Two-level: L1 in-memory LRU, L2 SQLite |
| **Trace Store** | Persist traces (phases, timings, cache hits) for observability |

## Path Routing

Paths are normalized (trailing slash stripped) and matched against registered patterns:

- `/wiki/entities/{name}/` → entity list
- `/wiki/entities/{name}/article.md` → article (default lang)
- `/wiki/entities/{name}/article.{lang}.md` → article (specific lang)
- `/wiki/entities/{name}/properties/{prop}.txt` → property value
- `/wiki/entities/{name}/relations/{relation}/` → relation targets
- `/wiki/search` → entity search
- `/wiki/sparql/result.csv` → SPARQL query

See [The Pattern](the-pattern.md) for applying this architecture to other data sources.
