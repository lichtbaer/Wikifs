import type { Stats } from "../types";

interface StatsViewProps {
  stats: Stats | null;
  loading: boolean;
  onClose: () => void;
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-700/60 bg-slate-800/80 px-4 py-3 text-center">
      <div className="font-mono text-xl font-semibold text-slate-100">{value}</div>
      <div className="text-xs text-slate-400 mt-0.5">{label}</div>
      {sub && <div className="text-xs text-slate-600 mt-0.5">{sub}</div>}
    </div>
  );
}

export function StatsView({ stats, loading, onClose }: StatsViewProps) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="max-h-[85vh] w-full max-w-lg overflow-auto rounded-xl border border-slate-700 bg-slate-900 shadow-2xl shadow-black/50">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-slate-700/60 px-5 py-4">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">◎</span>
            <h2 className="text-sm font-semibold text-slate-100">Statistiken</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full w-6 h-6 flex items-center justify-center text-slate-500 hover:bg-slate-700 hover:text-slate-300 transition-colors text-sm"
          >
            ×
          </button>
        </div>

        <div className="p-5">
          {loading ? (
            <div className="flex items-center justify-center py-8 gap-2 text-slate-500">
              <span className="inline-block w-4 h-4 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin" />
              <span className="text-sm">Lade…</span>
            </div>
          ) : stats ? (
            <div className="space-y-4">
              {/* Primary stats grid */}
              <div className="grid grid-cols-2 gap-3">
                <StatCard
                  label="Commands gesamt"
                  value={String(stats.count)}
                />
                <StatCard
                  label="Cache Hit Rate"
                  value={`${(stats.cache_hit_rate * 100).toFixed(1)}%`}
                />
              </div>

              {/* Cache hit rate bar */}
              <div>
                <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-2 rounded-full bg-green-500 transition-all"
                    style={{ width: `${stats.cache_hit_rate * 100}%` }}
                  />
                </div>
              </div>

              {/* Duration stats */}
              <div className="grid grid-cols-2 gap-3">
                <StatCard
                  label="Durchschnitt"
                  value={`${stats.avg_duration_ms.toFixed(0)}ms`}
                />
                <StatCard
                  label="Maximum"
                  value={`${stats.max_duration_ms.toFixed(0)}ms`}
                />
                <StatCard
                  label="P50 (Median)"
                  value={`${stats.p50_duration_ms.toFixed(0)}ms`}
                />
                <StatCard
                  label="P95"
                  value={`${stats.p95_duration_ms.toFixed(0)}ms`}
                />
              </div>

              {/* Commands by type */}
              {Object.keys(stats.commands_by_type).length > 0 && (
                <div className="rounded-lg border border-slate-700/60 bg-slate-800/60 p-4">
                  <h3 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-3">
                    Commands nach Typ
                  </h3>
                  <div className="space-y-2">
                    {Object.entries(stats.commands_by_type).map(([cmd, cnt]) => {
                      const maxCnt = Math.max(...Object.values(stats.commands_by_type));
                      const pct = (cnt / maxCnt) * 100;
                      return (
                        <div key={cmd} className="flex items-center gap-3">
                          <span className="font-mono text-xs text-slate-300 w-16 shrink-0">{cmd}</span>
                          <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                            <div
                              className="h-1.5 bg-blue-500 rounded-full"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <span className="font-mono text-xs text-slate-400 w-8 text-right shrink-0">
                            {cnt}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <div className="text-2xl mb-2 opacity-40">📊</div>
              <p className="text-sm text-slate-500">Keine Daten verfügbar.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
