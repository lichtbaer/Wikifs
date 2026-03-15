import type { Stats } from "../types";

interface StatsViewProps {
  stats: Stats | null;
  loading: boolean;
  onClose: () => void;
}

export function StatsView({ stats, loading, onClose }: StatsViewProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="max-h-[80vh] w-full max-w-md overflow-auto rounded-lg border border-gray-200 bg-white p-6 shadow-lg">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Statistiken</h2>
          <button
            type="button"
            onClick={onClose}
            className="rounded px-2 py-1 text-sm hover:bg-gray-100"
          >
            Schließen
          </button>
        </div>
        {loading ? (
          <p className="text-sm text-gray-500">Lade...</p>
        ) : stats ? (
          <div className="space-y-3 text-sm">
            <div>
              <span className="text-gray-500">Total Commands:</span>{" "}
              <span className="font-medium">{stats.count}</span>
            </div>
            <div>
              <span className="text-gray-500">Avg Duration:</span>{" "}
              <span className="font-medium">{stats.avg_duration_ms.toFixed(1)} ms</span>
            </div>
            <div>
              <span className="text-gray-500">P50 Duration:</span>{" "}
              <span className="font-medium">{stats.p50_duration_ms.toFixed(1)} ms</span>
            </div>
            <div>
              <span className="text-gray-500">P95 Duration:</span>{" "}
              <span className="font-medium">{stats.p95_duration_ms.toFixed(1)} ms</span>
            </div>
            <div>
              <span className="text-gray-500">Max Duration:</span>{" "}
              <span className="font-medium">{stats.max_duration_ms.toFixed(1)} ms</span>
            </div>
            <div>
              <span className="text-gray-500">Cache Hit Rate:</span>{" "}
              <span className="font-medium">{(stats.cache_hit_rate * 100).toFixed(1)}%</span>
            </div>
            {Object.keys(stats.commands_by_type).length > 0 && (
              <div>
                <span className="text-gray-500">Commands by Type:</span>
                <ul className="mt-1 list-inside list-disc">
                  {Object.entries(stats.commands_by_type).map(([cmd, cnt]) => (
                    <li key={cmd}>
                      {cmd}: {cnt}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-gray-500">Keine Daten.</p>
        )}
      </div>
    </div>
  );
}
