import { useCallback, useEffect, useState } from "react";
import {
  clearServerCache,
  fetchErrors,
  fetchTraces,
  type ErrorListItem,
  type TraceListItem,
} from "../api/wikifs";

interface ObservabilityViewProps {
  onClose: () => void;
}

type Tab = "traces" | "errors";

export function ObservabilityView({ onClose }: ObservabilityViewProps) {
  const [tab, setTab] = useState<Tab>("traces");
  const [traces, setTraces] = useState<TraceListItem[] | null>(null);
  const [errors, setErrors] = useState<ErrorListItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [cacheMsg, setCacheMsg] = useState<string | null>(null);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErrMsg(null);
    try {
      const [t, e] = await Promise.all([fetchTraces(30), fetchErrors(30)]);
      setTraces(t);
      setErrors(e);
    } catch (e) {
      setErrMsg(e instanceof Error ? e.message : String(e));
      setTraces(null);
      setErrors(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleClearCache = async () => {
    setCacheMsg(null);
    try {
      const n = await clearServerCache();
      setCacheMsg(`Server-Cache geleert (${n} Einträge).`);
      await load();
    } catch (e) {
      setCacheMsg(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="max-h-[88vh] w-full max-w-2xl overflow-hidden flex flex-col rounded-xl border border-slate-700 bg-slate-900 shadow-2xl shadow-black/50">
        <div className="flex items-center justify-between border-b border-slate-700/60 px-5 py-4 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-slate-400">◈</span>
            <h2 className="text-sm font-semibold text-slate-100">Observability</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full w-6 h-6 flex items-center justify-center text-slate-500 hover:bg-slate-700 hover:text-slate-300 transition-colors text-sm"
          >
            ×
          </button>
        </div>

        <div className="flex gap-1 border-b border-slate-700/60 px-4 py-2 shrink-0">
          <button
            type="button"
            onClick={() => setTab("traces")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md ${
              tab === "traces"
                ? "bg-slate-700 text-slate-100"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            Traces
          </button>
          <button
            type="button"
            onClick={() => setTab("errors")}
            className={`px-3 py-1.5 text-xs font-medium rounded-md ${
              tab === "errors"
                ? "bg-slate-700 text-slate-100"
                : "text-slate-500 hover:text-slate-300"
            }`}
          >
            Fehler
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => load()}
            className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 border border-slate-600 rounded-md"
          >
            Aktualisieren
          </button>
          <button
            type="button"
            onClick={handleClearCache}
            className="px-3 py-1.5 text-xs text-amber-200/90 hover:text-amber-100 border border-amber-700/50 rounded-md bg-amber-950/30"
          >
            Cache leeren
          </button>
        </div>

        <div className="flex-1 overflow-auto p-4 min-h-[200px]">
          {cacheMsg && (
            <p className="text-xs text-slate-400 mb-3 font-mono">{cacheMsg}</p>
          )}
          {errMsg && (
            <p className="text-xs text-red-400 mb-3">{errMsg}</p>
          )}
          {loading ? (
            <div className="flex items-center justify-center py-12 gap-2 text-slate-500">
              <span className="inline-block w-4 h-4 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin" />
              <span className="text-sm">Lade…</span>
            </div>
          ) : tab === "traces" ? (
            traces && traces.length > 0 ? (
              <ul className="space-y-2 font-mono text-xs">
                {traces.map((t) => (
                  <li
                    key={t.trace_id}
                    className="rounded border border-slate-700/50 bg-slate-800/40 px-3 py-2 text-slate-300"
                  >
                    <div className="flex justify-between gap-2 text-slate-500 text-[10px] uppercase tracking-wide">
                      <span>{t.timestamp.slice(0, 19)}</span>
                      <span
                        className={
                          t.exit_code === 0 ? "text-green-500/90" : "text-amber-500/90"
                        }
                      >
                        exit {t.exit_code} · {t.total_duration_ms.toFixed(0)} ms
                      </span>
                    </div>
                    <div className="text-slate-200 mt-1">
                      <span className="text-blue-400">{t.command}</span>{" "}
                      <span className="text-slate-400 break-all">{t.path}</span>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-slate-500 text-center py-8">Keine Traces.</p>
            )
          ) : errors && errors.length > 0 ? (
            <ul className="space-y-2 font-mono text-xs">
              {errors.map((e) => (
                <li
                  key={e.error_id}
                  className="rounded border border-slate-700/50 bg-slate-800/40 px-3 py-2 text-slate-300"
                >
                  <div className="flex justify-between gap-2 text-slate-500 text-[10px]">
                    <span>{e.timestamp.slice(0, 19)}</span>
                    <span>
                      {e.category}/{e.severity}
                      {e.resolved ? " · resolved" : ""}
                    </span>
                  </div>
                  <p className="text-slate-200 mt-1 break-words">{e.message}</p>
                  <p className="text-slate-600 mt-0.5 truncate">{e.error_id}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-slate-500 text-center py-8">Keine Fehler.</p>
          )}
        </div>
      </div>
    </div>
  );
}
