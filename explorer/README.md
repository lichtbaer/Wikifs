# WikiFS Explorer

Visuelle Oberfläche für WikiFS — zeigt Commands, Trace-Timeline und ermöglicht Navigation.

## Start

```bash
cd explorer && npm install && npm run dev
# → http://localhost:5173
```

Parallel: `wikifs serve --port 8000` in einem zweiten Terminal.

## Features

- **Command Input**: ls, cat, grep, search mit Auto-Erkennung
- **Output Panel**: Markdown-Rendering, JSON-Formatierung, klickbare Einträge
- **Trace Timeline**: Phasen mit Timings und Cache-Status
- **Breadcrumb-Navigation**: Pfad-Segmente und Back-Button
- **Stats-View**: Aggregate von GET /stats
