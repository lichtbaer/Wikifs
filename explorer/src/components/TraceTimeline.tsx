import type { Trace } from "../types";

interface TraceTimelineProps {
  trace: Trace | null | undefined;
}

function durationColor(ms: number): string {
  if (ms < 100) return "text-green-600";
  if (ms < 500) return "text-yellow-600";
  return "text-red-600";
}

function statusIcon(result: string, cacheHit: boolean | null | undefined): string {
  if (result === "error") return "✗";
  if (cacheHit === true) return "HIT";
  if (cacheHit === false) return "MISS";
  return "✓";
}

export function TraceTimeline({ trace }: TraceTimelineProps) {
  if (!trace) {
    return (
      <div className="rounded border border-gray-200 bg-gray-50 p-4 text-sm text-gray-500">
        Kein Trace. Führen Sie einen Befehl aus.
      </div>
    );
  }

  const { phases, total_duration_ms, api_calls, cache_hits, cache_misses } = trace;

  return (
    <div className="flex flex-col">
      <div className="space-y-2">
        {phases.map((p, i) => (
          <div
            key={i}
            className="flex items-start gap-2 rounded border border-gray-200 bg-white p-2 text-sm"
          >
            <span className="text-gray-400">▸</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium">{p.phase}</span>
                <span className={`font-mono ${durationColor(p.duration_ms)}`}>
                  {Math.round(p.duration_ms)}ms
                </span>
                <span
                  className={
                    p.result === "error"
                      ? "text-red-600"
                      : p.cache_hit === false
                        ? "text-amber-600"
                        : "text-green-600"
                  }
                >
                  {statusIcon(p.result, p.cache_hit)}
                </span>
              </div>
              {p.api_url && (
                <details className="mt-1">
                  <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700">
                    API URL
                  </summary>
                  <pre className="mt-1 overflow-x-auto text-xs text-gray-600 break-all">
                    {p.api_url}
                  </pre>
                </details>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="mt-3 rounded border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600">
        Total: {Math.round(total_duration_ms)}ms | API: {api_calls} | Cache: {cache_hits} hits,{" "}
        {cache_misses} misses
      </div>
    </div>
  );
}
