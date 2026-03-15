# Explorer UI

The WikiFS Explorer is a web interface for running commands, viewing output, and inspecting traces.

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

## Features

| Feature | Description |
|---------|-------------|
| **Command Input** | Enter `ls`, `cat`, `grep`, `search` with auto-detection. Supports history. |
| **Output Panel** | Markdown rendering, JSON formatting, clickable entity links for navigation |
| **Trace Timeline** | Phases with timings, cache hit status, API URLs |
| **Breadcrumb** | Path segments with back navigation |
| **Stats** | Aggregate statistics from the server (total commands, latency, cache hit rate) |
| **Quick Actions** | One-click commands for common operations |

## Usage

1. Type a command in the input (e.g. `ls /wiki/entities/Frankfurt_am_Main/`) and press Enter.
2. View the output in the Output panel. Click entity names to navigate.
3. Inspect the Trace Timeline to see which phases ran and how long they took.
4. Use the Breadcrumb to go back to parent paths.
5. Click "Stats" to see aggregate performance data.

## Server Offline

If the WikiFS server is not running, a warning appears. Start it with `wikifs serve` before using the Explorer.
