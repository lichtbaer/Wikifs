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
      <div className="rounded border border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
        Geben Sie einen Befehl ein und klicken Sie auf Run.
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
      {errorType && (
        <div className="mb-2">
          <span className="text-xs font-medium text-red-600">Error: {errorType}</span>
        </div>
      )}
      {suggestions && suggestions.length > 0 && exitCode === 2 && (
        <div className="mb-2">
          <span className="text-xs text-gray-600">Vorschläge: </span>
          {suggestions.map((s) => {
            const parentPath = currentPath.replace(/\/[^/]+\/?$/, "/") || "/wiki/";
            const suggestionPath = s.startsWith("/") ? s : parentPath + s + "/";
            return (
              <button
                key={s}
                type="button"
                onClick={() => onNavigate(suggestionPath)}
                className="mr-2 text-xs text-blue-600 hover:underline"
              >
                {s}
              </button>
            );
          })}
        </div>
      )}
      <div
        className={`flex-1 overflow-auto rounded border p-4 font-mono text-sm ${
          isError ? "border-red-500 bg-red-50 text-red-900" : "border-gray-200 bg-white"
        }`}
      >
        {looksLikeLs && entries.length > 1 ? (
          <div className="space-y-1">
            {entries.map((entry) => {
              const isDir = entry.endsWith("/");
              const isClickable = isDir || /\.(md|txt|json)$/.test(entry);
              return (
                <div key={entry}>
                  {isClickable ? (
                    <button
                      type="button"
                      onClick={() => handleClick(entry)}
                      className="text-left hover:underline focus:underline"
                    >
                      {entry}
                    </button>
                  ) : (
                    <span>{entry}</span>
                  )}
                </div>
              );
            })}
          </div>
        ) : isJsonLike(output) ? (
          <pre className="whitespace-pre-wrap break-words text-xs">
            {formatJson(output)}
          </pre>
        ) : (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown>{output}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
