# Configuration

WikiFS reads configuration from `config.toml`. The file is optional; defaults apply if missing.

## Environment variables (API keys)

For agent / natural language queries, the LLM provider needs an API key. Set it via environment variables (e.g. from a `.env` file):

- **OpenAI** (`openai:gpt-4o` etc.): `OPENAI_API_KEY`
- **Anthropic** (Claude): `ANTHROPIC_API_KEY`

Copy `.env.example` to `.env`, then fill in the key that matches your `config.toml` → `[agent]` → `default_model`. Do not commit `.env` (it is in `.gitignore`).

## Location

- Project root: `config.toml`
- User config: `~/.wikifs/config.toml`

Configs are merged; project root overrides user config.

## Reference

### [wikifs]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_language` | string | `"de"` | Default language for `article.md` |
| `supported_languages` | list | `["de", "en"]` | Languages for `article.{lang}.md` |

### [cache]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `l1_max_size` | int | `256` | L1 (in-memory) cache max entries |
| `l1_ttl_seconds` | int | `3600` | L1 entry TTL (1 hour) |
| `l2_ttl_seconds` | int | `86400` | L2 (SQLite) entry TTL (24 hours) |
| `l2_db_path` | string | `"~/.wikifs/cache.db"` | L2 database path |

### [tracing]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Enable trace collection |
| `db_path` | string | `"~/.wikifs/traces.db"` | Trace database path |

### [api]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `wikidata_base_url` | string | `"https://www.wikidata.org"` | Wikidata base URL |
| `wikipedia_base_url` | string | `"https://{lang}.wikipedia.org"` | Wikipedia URL template |
| `request_timeout_seconds` | int | `10` | HTTP request timeout |
| `user_agent` | string | `"WikiFS/0.1 (...)"` | User-Agent header |

### [pagination]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_limit` | int | `100` | Default result limit for search |
| `max_limit` | int | `500` | Maximum allowed limit |

### [agent]

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `default_model` | string | `"openai:gpt-4o"` | Model for the agent (e.g. `openai:gpt-4o`, `anthropic:claude-sonnet-4-20250514`) |
| `max_tool_calls` | int | `20` | Maximum number of tool calls per agent run |

The chosen model requires the corresponding API key (e.g. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`); see environment variables above.

## Example

```toml
[wikifs]
default_language = "en"
supported_languages = ["en", "de"]

[cache]
l1_max_size = 512
l2_ttl_seconds = 43200

[tracing]
enabled = true
db_path = "~/.wikifs/traces.db"
```
