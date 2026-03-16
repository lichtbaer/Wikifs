# Explorer UI

The WikiFS Explorer is a web interface for running commands, viewing output, and inspecting traces. It offers two modes: **Manual** (shell-style commands) and **Agent** (natural-language questions).

## Starting the Explorer

1. **Start the WikiFS HTTP server** (in one terminal):

```bash
wikifs serve --port 8000
```

2. **Start the Explorer** (in another terminal):

```bash
cd explorer
npm install
npm run dev
```

3. Open [http://localhost:5173](http://localhost:5173) in your browser.

## Two Modes

| Mode | Description |
|------|-------------|
| **Manual** | Enter WikiFS commands (`ls`, `cat`, `grep`, `search`) with paths. Output and trace timeline show results. |
| **Agent** | Ask natural-language questions. The AI agent runs WikiFS tools and shows steps and final answer. |

Switch between them via the **Manual** and **Agent** tabs in the header.

## Features (Manual mode)

| Feature | Description |
|---------|-------------|
| **Command Input** | Enter `ls`, `cat`, `grep`, `search` with auto-detection. Supports history. |
| **Output Panel** | Markdown rendering, JSON formatting, clickable entity links for navigation |
| **Trace Timeline** | Phases with timings, cache hit status, API URLs |
| **Breadcrumb** | Path segments with back navigation |
| **Stats** | Aggregate statistics from the server (total commands, latency, cache hit rate) |
| **Quick Actions** | One-click commands for common operations |

## Features (Agent mode)

| Feature | Description |
|---------|-------------|
| **Ask the Agent** | Text field for a natural-language question; optional model selector (e.g. GPT-4o, Claude Sonnet) |
| **Example questions** | One-click example prompts (e.g. "Einwohner von Berlin", "Frankfurt und München vergleichen") |
| **Agent Steps** | List of WikiFS commands executed (ls, cat, grep, search) with path, status, timing, and optional trace |
| **Agent Answer** | Final answer from the agent with summary (total commands, duration, cache hits) |

The Agent tab uses the streaming API so you see each step as it completes. See [Agent](agent.md) for how the agent works and which tools it uses.

## Usage (Manual)

1. Type a command in the input (e.g. `ls /wiki/entities/Frankfurt_am_Main/`) and press Enter.
2. View the output in the Output panel. Click entity names to navigate.
3. Inspect the Trace Timeline to see which phases ran and how long they took.
4. Use the Breadcrumb to go back to parent paths.
5. Click "Stats" to see aggregate performance data.

## Usage (Agent)

1. Switch to the **Agent** tab.
2. Enter a question (e.g. "Wie viele Einwohner hat Berlin?") or click an example question.
3. Optionally select a model (default: GPT-4o).
4. Click **Ask**. Watch **Agent Steps** for each command and **Agent Answer** for the final response.

## Prerequisites

- **Server:** The WikiFS HTTP server must be running (`wikifs serve`). If not, a warning is shown.
- **Agent:** For the Agent tab you need an API key for the chosen model: set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` (see [Configuration](configuration.md)).

## Server Offline

If the WikiFS server is not running, a warning appears. Start it with `wikifs serve` before using the Explorer.
