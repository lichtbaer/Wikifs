import type { Trace } from "../types";

interface TraceTimelineProps {
  trace: Trace | null | undefined;
}

function durationBarColor(ms: number): string {
  if (ms < 100) return "bg-green-500";
  if (ms < 500) return "bg-yellow-500";
  return "bg-red-500";
}

function durationTextColor(ms: number): string {
  if (ms < 100) return "text-green-400";
  if (ms < 500) return "text-yellow-400";
  return "text-red-400";
}

function phaseIcon(phase: string): string {
  const lower = phase.toLowerCase();
  if (lower.includes("fetch") || lower.includes("http") || lower.includes("api")) return "⚡";
  if (lower.includes("cache")) return "💾";
  if (lower.includes("parse") || lower.includes("process")) return "🔄";
  if (lower.includes("search")) return "🔍";
  if (lower.includes("render") || lower.includes("format")) return "✨";
  return "▸";
}

function StatusBadge({ result, cacheHit }: { result: string; cacheHit: boolean | null | undefined }) {
  if (result === "error") {
    return (
      <span className="rounded-full bg-red-900/60 border border-red-700/50 px-1.5 py-0.5 text-xs font-medium text-red-400">
        ✗ error
      </span>
    );
  }
  if (cacheHit === true) {
    return (
      <span className="rounded-full bg-green-900/60 border border-green-700/50 px-1.5 py-0.5 text-xs font-medium text-green-400">
        💾 HIT
      </span>
    );
  }
  if (cacheHit === false) {
    return (
      <span className="rounded-full bg-amber-900/60 border border-amber-700/50 px-1.5 py-0.5 text-xs font-medium text-amber-400">
        MISS
      </span>
    );
  }
  return (
    <span className="rounded-full bg-green-900/60 border border-green-700/50 px-1.5 py-0.5 text-xs font-medium text-green-400">
      ✓
    </span>
  );
}

export function TraceTimeline({ trace }: TraceTimelineProps) {
  if (!trace) {
    return (
      <div className="flex-1 rounded-lg border border-slate-700/60 bg-slate-900/60 p-6 text-sm">
        <div className="flex flex-col items-center justify-center h-full min-h-[180px] text-center">
          <div className="text-3xl mb-2 opacity-40">⏱</div>
          <p className="text-slate-500 text-xs">Kein Trace. Führe einen Befehl aus.</p>
        </div>
      </div>
    );
  }

  const { phases, total_duration_ms, api_calls, cache_hits, cache_misses } = trace;
  const maxPhaseDuration = Math.max(...phases.map((p) => p.duration_ms), 1);

  return (
    <div className="flex flex-col gap-2">
      <div className="space-y-1.5">
        {phases.map((p, i) => (
          <div
            key={i}
            className="rounded-lg border border-slate-700/60 bg-slate-900/60 p-2.5"
          >
            <div className="flex items-center justify-between gap-2 mb-1.5">
              <div className="flex items-center gap-1.5 min-w-0">
                <span className="text-xs shrink-0">{phaseIcon(p.phase)}</span>
                <span className="text-xs font-medium text-slate-200 truncate">{p.phase}</span>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <span className={`font-mono text-xs ${durationTextColor(p.duration_ms)}`}>
                  {Math.round(p.duration_ms)}ms
                </span>
                <StatusBadge result={p.result} cacheHit={p.cache_hit} />
              </div>
            </div>
            {/* Timing bar */}
            <div className="h-1 w-full rounded-full bg-slate-800">
              <div
                className={`h-1 rounded-full transition-all ${durationBarColor(p.duration_ms)}`}
                style={{ width: `${Math.max((p.duration_ms / maxPhaseDuration) * 100, 2)}%` }}
              />
            </div>
            {p.api_url && (
              <details className="mt-1.5">
                <summary className="cursor-pointer text-xs text-slate-600 hover:text-slate-400 transition-colors select-none">
                  API URL ›
                </summary>
                <pre className="mt-1 overflow-x-auto text-xs text-slate-500 break-all leading-relaxed">
                  {p.api_url}
                </pre>
              </details>
            )}
          </div>
        ))}
      </div>

      {/* Summary */}
      <div className="rounded-lg border border-slate-700/60 bg-slate-800/60 px-3 py-2">
        <div className="grid grid-cols-4 gap-2 text-center">
          <div>
            <div className={`font-mono text-sm font-semibold ${durationTextColor(total_duration_ms)}`}>
              {Math.round(total_duration_ms)}ms
            </div>
            <div className="text-xs text-slate-500">Gesamt</div>
          </div>
          <div>
            <div className="font-mono text-sm font-semibold text-slate-200">{api_calls}</div>
            <div className="text-xs text-slate-500">API-Calls</div>
          </div>
          <div>
            <div className="font-mono text-sm font-semibold text-green-400">{cache_hits}</div>
            <div className="text-xs text-slate-500">Cache HIT</div>
          </div>
          <div>
            <div className="font-mono text-sm font-semibold text-amber-400">{cache_misses}</div>
            <div className="text-xs text-slate-500">Cache MISS</div>
          </div>
        </div>
      </div>
    </div>
  );
}
