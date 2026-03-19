# WikiFS

Virtual filesystem over Wikipedia and Wikidata for AI agents. Exposes Wikipedia articles and the Wikidata knowledge graph via familiar shell commands (`ls`, `cat`, `grep`, `search`). Under the hood: structured API calls and SPARQL queries. Proof of concept for the pattern "Filesystem as Integration Layer".

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows

pip install -e .
wikifs ls /wiki/entities/Frankfurt_am_Main/
```

First command in under 5 minutes.

## Commands

| Command | Example |
|---------|---------|
| `ls` | `wikifs ls /wiki/entities/Frankfurt_am_Main/` |
| Q-ID-Pfade | `wikifs ls /wiki/entities/Q64/` (Auflösung zur Wikipedia-Überschrift, z. B. Berlin) |
| `ls -l` | `wikifs ls -l /wiki/entities/Frankfurt_am_Main/` |
| `cat` | `wikifs cat /wiki/entities/Frankfurt_am_Main/article.md` |
| `head` / `tail` | `wikifs head -n 40 /wiki/entities/Frankfurt_am_Main/article.md` |
| `ls` Kategorien | `wikifs ls /wiki/entities/Berlin/categories/` |
| `ls` Links | `wikifs ls /wiki/entities/Berlin/links/` |
| `cat` | `wikifs cat /wiki/entities/Frankfurt_am_Main/properties/population.txt` |
| `grep` | `wikifs grep "Goethe" /wiki/entities/Frankfurt_am_Main/` |
| `grep -i -c` | `wikifs grep -i -c "goethe" /wiki/entities/Frankfurt_am_Main/` |
| `search` | `wikifs search "Goethe" --type entity --limit 5` |
| `search --sparql` | `wikifs search --sparql "SELECT ?x WHERE { ?x wdt:P31 wd:Q515 } LIMIT 5"` |
| `stats` | `wikifs stats` |
| `traces` | `wikifs traces --slow 500` |
| `traces` | `wikifs traces --path "/wiki/entities/*/article.md"` |
| `traces` | `wikifs traces --command cat` |
| `traces clear` | `wikifs traces clear --older-than 7` |
| `cache stats` | `wikifs cache stats` |
| `cache clear` | `wikifs cache clear` |
| `doctor` | `wikifs doctor` — Pfade, Wikimedia-API, optionale Agent-Keys |

## Architecture

```
Agent → JSON Command → Interpreter → Path Router → Backend Client → Response Formatter → Agent
                              ↓
                    Cache (L1 LRU + L2 SQLite)
                              ↓
                    Trace Store (SQLite)
```

See ADRs for design decisions.

## HTTP API / Explorer

- **`POST /execute`** akzeptiert optional ein Feld **`lang`** (z. B. `de`, `en`), sofern es in `supported_languages` der Konfiguration steht; überschreibt die Standard-Wikipedia-Sprache für diese Anfrage.
- Der **Explorer** bietet eine Sprachauswahl (manueller Modus), **Observability** (letzte Traces, Fehler, Server-Cache leeren) und **Stats**.

## Configuration

**Environment variables (API keys):** For agent / natural language queries, set the LLM API key via environment variables. Copy `.env.example` to `.env` and fill in at least one key depending on `config.toml` → `[agent]` → `default_model` (e.g. `OPENAI_API_KEY` for `openai:gpt-4o`, `ANTHROPIC_API_KEY` for Anthropic models).

`config.toml` (optional, in project root or `~/.wikifs/`):

```toml
[wikifs]
default_language = "de"
supported_languages = ["de", "en"]

[cache]
l1_max_size = 256
l1_ttl_seconds = 3600
l2_ttl_seconds = 86400
l2_db_path = "~/.wikifs/cache.db"

[tracing]
enabled = true
db_path = "~/.wikifs/traces.db"

[api]
wikidata_base_url = "https://www.wikidata.org"
wikipedia_base_url = "https://{lang}.wikipedia.org"
request_timeout_seconds = 10
user_agent = "WikiFS/0.1 (https://github.com/Lichtbaer/wikifs)"

[pagination]
default_limit = 100
max_limit = 500
```

## Observability

- **`wikifs stats`** — Total commands, avg/P50/P95/max duration, cache hit rate, commands by type
- **`wikifs traces --slow 500`** — Traces slower than 500 ms
- **`wikifs traces --path "/wiki/entities/*/article.md"`** — Filter by path pattern
- **`wikifs traces --command cat`** — Filter by command
- **`wikifs traces clear --older-than 7`** — Delete traces older than 7 days
- **`wikifs cache stats`** — L1/L2 hits, hit rate, sizes

## The Pattern

"Filesystem as Integration Layer" — arbitrary structured data sources exposed via a POSIX-like abstraction for AI agents. WikiFS demonstrates this with Wikipedia and Wikidata. See the concept paper for the full pattern.

## Demo

```bash
python scripts/demo.py
```

Runs the reference flow (Frankfurt → Hessen → Deutschland), shows trace summary, and a second run to demonstrate cache effect.

## Docker

Run API and Explorer in containers:

```bash
docker compose up --build
```

Then open [http://localhost:8080](http://localhost:8080). The Explorer UI is served by Nginx and proxies `/api` to the FastAPI backend. Cache and trace data are stored in a Docker volume (`wikifs_data`). For the agent to work, copy `.env.example` to `.env` and set e.g. `OPENAI_API_KEY`. To use a custom config, set `WIKIFS_DATA_DIR=/data` (default) and optionally mount `config.docker.toml` as the config file; the image uses `WIKIFS_DATA_DIR` to place SQLite DBs under `/data`.

## Development

```bash
ruff check .
mypy --strict wikifs/
pytest
```

## License

MIT
