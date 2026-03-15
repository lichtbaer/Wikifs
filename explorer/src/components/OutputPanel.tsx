import ReactMarkdown from "react-markdown";

interface OutputPanelProps {
  output: string;
  exitCode: number | null;
  errorType: string | null;
  suggestions: string[] | null;
  currentPath: string;
  onNavigate: (path: string) => void;
}

function isJsonLike(text: string): boolean {
  const t = text.trim();
  return (t.startsWith("{") && t.endsWith("}")) || (t.startsWith("[") && t.endsWith("]"));
}

function formatJson(text: string): string {
  try {
    const parsed = JSON.parse(text);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return text;
  }
}

function parseLsOutput(output: string): string[] {
  const lines = output.split("\n").filter((l) => l.trim());
  const entries: string[] = [];
  for (const line of lines) {
    const first = line.split(/\t/)[0]?.trim() ?? line.trim();
    if (first) entries.push(first);
  }
  return entries;
}

function entryIcon(entry: string): string {
  if (entry.endsWith("/")) return "📂";
  if (entry.endsWith(".md")) return "📄";
  if (entry.endsWith(".json")) return "{}";
  if (entry.endsWith(".txt")) return "📝";
  return "·";
}

function entryColor(entry: string): string {
  if (entry.endsWith("/")) return "text-blue-400 hover:text-blue-300";
  if (entry.endsWith(".md")) return "text-green-400 hover:text-green-300";
  if (entry.endsWith(".json")) return "text-yellow-400 hover:text-yellow-300";
  return "text-slate-300 hover:text-slate-200";
}

export function OutputPanel({
  output,
  exitCode,
  errorType,
  suggestions,
  currentPath,
  onNavigate,
}: OutputPanelProps) {
  if (!output && exitCode === null) {
    return (
      <div className="flex-1 rounded-lg border border-slate-700/60 bg-slate-900/60 p-6 text-sm">
        <div className="flex flex-col items-center justify-center h-full min-h-[180px] text-center">
          <div className="text-4xl mb-3 opacity-50">🗂</div>
          <p className="text-slate-400 mb-4">Bereit. Befehl eingeben und <kbd className="font-mono text-xs bg-slate-800 border border-slate-600 px-1.5 py-0.5 rounded">↵ Enter</kbd> drücken.</p>
          <div className="flex flex-col gap-1 text-left">
            {[
              "ls /wiki/entities/",
              "cat /wiki/entities/Berlin/article.md",
              'search "Frankfurt"',
            ].map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => onNavigate(ex.startsWith("ls ") ? ex.slice(3) : ex)}
                className="font-mono text-xs text-slate-500 hover:text-blue-400 transition-colors text-left"
              >
                $ {ex}
              </button>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const isError = exitCode === 1 || exitCode === 2;
  const entries = parseLsOutput(output);
  const looksLikeLs =
    entries.length > 0 &&
    entries.every(
      (e) =>
        e.endsWith("/") ||
        /\.(md|txt|json)$/.test(e) ||
        /^[a-zA-Z0-9_]+$/.test(e) ||
        e.includes("_")
    );

  const basePath = currentPath.endsWith("/") ? currentPath : currentPath + "/";
  const handleClick = (entry: string) => {
    const isDir = entry.endsWith("/");
    const name = entry.replace(/\/$/, "");
    const fullPath = basePath + name + (isDir ? "/" : "");
    onNavigate(fullPath);
  };

  return (
    <div className="flex flex-1 flex-col overflow-auto">
      {/* Error / suggestions header */}
      {(errorType || (suggestions && suggestions.length > 0 && exitCode === 2)) && (
        <div className="mb-2 space-y-1">
          {errorType && (
            <div className="flex items-center gap-1.5 text-xs">
              <span className="text-red-400">✗</span>
              <span className="text-red-400 font-medium">{errorType}</span>
            </div>
          )}
          {suggestions && suggestions.length > 0 && exitCode === 2 && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="text-slate-500">Meintest du:</span>
              {suggestions.map((s) => {
                const parentPath = currentPath.replace(/\/[^/]+\/?$/, "/") || "/wiki/";
                const suggestionPath = s.startsWith("/") ? s : parentPath + s + "/";
                return (
                  <button
                    key={s}
                    type="button"
                    onClick={() => onNavigate(suggestionPath)}
                    className="rounded border border-blue-500/40 bg-blue-900/30 px-2 py-0.5 text-blue-400 hover:bg-blue-900/50 hover:text-blue-300 transition-colors font-mono"
                  >
                    {s}
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      <div
        className={`flex-1 overflow-auto rounded-lg border p-4 font-mono text-sm ${
          isError
            ? "border-red-700/50 bg-red-950/40 text-red-300"
            : "border-slate-700/60 bg-slate-900/60 text-slate-100"
        }`}
      >
        {looksLikeLs && entries.length > 1 ? (
          <div className="space-y-0.5">
            {entries.map((entry) => {
              const isClickable = entry.endsWith("/") || /\.(md|txt|json)$/.test(entry);
              const icon = entryIcon(entry);
              const colorClass = entryColor(entry);
              return (
                <div
                  key={entry}
                  className="group flex items-center gap-2 rounded px-1 py-0.5 hover:bg-slate-800/60 transition-colors"
                >
                  <span className="text-xs w-4 text-center shrink-0 opacity-60">{icon}</span>
                  {isClickable ? (
                    <button
                      type="button"
                      onClick={() => handleClick(entry)}
                      className={`text-left transition-colors ${colorClass}`}
                    >
                      {entry}
                    </button>
                  ) : (
                    <span className="text-slate-400">{entry}</span>
                  )}
                </div>
              );
            })}
          </div>
        ) : isJsonLike(output) ? (
          <pre className="whitespace-pre-wrap break-words text-xs text-green-300">
            {formatJson(output)}
          </pre>
        ) : (
          <div className="prose-terminal max-w-none text-sm leading-relaxed">
            <ReactMarkdown>{output}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
