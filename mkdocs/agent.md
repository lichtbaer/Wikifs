# Agent

The WikiFS Agent is an AI assistant that uses WikiFS as tools to answer natural-language questions about Wikipedia and Wikidata. It is built with [Pydantic AI](https://ai.pydantic.dev/) and uses an LLM (e.g. OpenAI GPT-4o, Anthropic Claude) to plan and execute filesystem-like commands.

## Concept

The agent has access to four WikiFS tools. Given a question, the LLM decides which commands to run (e.g. search for entities, list a directory, read an article) and interprets the results to produce a final answer. All tool calls are executed via the same interpreter used by the CLI and HTTP API, so traces and cache behave consistently.

## Tools

| Tool | Description | Example |
|------|-------------|---------|
| **wikifs_ls** | List directory contents | `/wiki/entities/Berlin/`, `/wiki/entities/Berlin/properties/` |
| **wikifs_cat** | Read file contents | `article.md`, `summary.md`, `properties/population.txt` |
| **wikifs_grep** | Search within a specific entity | Pattern + path to entity directory |
| **wikifs_search** | Search across entities to discover them | Query string, optional type and limit |

The agent uses these to navigate the knowledge graph, read articles and properties, and combine information into an answer. It is instructed to cite WikiFS paths as sources.

## Usage

### CLI

Run the agent from the command line:

```bash
wikifs agent "Wie viele Einwohner hat Berlin?"
```

Options:

| Option | Description |
|--------|-------------|
| `--model` | Model override (e.g. `openai:gpt-4o`, `anthropic:claude-sonnet-4-20250514`) |
| `--config` | Path to `config.toml` |

The answer is printed to stdout; executed commands are listed on stderr.

### HTTP API

- **POST /agent** — Run the agent once. Request body: `{"query": "string", "model": "optional"}`. Response: `answer`, `commands_executed`, `total_commands`, `total_duration_ms`. See [API Reference](api.md#post-agent).

- **POST /agent/stream** — Run the agent with Server-Sent Events. Same body. Events: `agent_start`, `thinking`, `tool_call`, `tool_result`, `answer`, `error`, `done`. See [API Reference](api.md#post-agentstream).

### Explorer UI

In the [Explorer](explorer.md), switch to the **Agent** tab:

1. Enter a natural-language question in the text field.
2. Optionally choose a model (e.g. GPT-4o, Claude Sonnet).
3. Use the example questions or type your own, then click **Ask**.
4. Watch **Agent Steps** (each WikiFS command and result) and **Agent Answer** (final response).

The UI uses the streaming endpoint so you see steps as they complete.

## Configuration

Agent behaviour is configured in `config.toml` under the `[agent]` section:

- **default_model** — Model used when none is specified (e.g. `openai:gpt-4o`).
- **max_tool_calls** — Maximum number of tool calls per run (default: 20).

The LLM provider requires an API key via environment variables:

- **OpenAI:** `OPENAI_API_KEY`
- **Anthropic:** `ANTHROPIC_API_KEY`

See [Configuration](configuration.md) for full reference and `.env` setup.
