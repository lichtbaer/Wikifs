import { useState, useCallback, useEffect } from "react";
import { useWikiFS } from "./hooks/useWikiFS";
import { fetchStats, checkHealth } from "./api/wikifs";
import { CommandInput } from "./components/CommandInput";
import { QuickActions } from "./components/QuickActions";
import { OutputPanel } from "./components/OutputPanel";
import { TraceTimeline } from "./components/TraceTimeline";
import { Breadcrumb } from "./components/Breadcrumb";
import { StatsView } from "./components/StatsView";
import { AgentPanel } from "./components/AgentPanel";
import type { Stats } from "./types";

type TabMode = "manual" | "agent";

function App() {
  const [tabMode, setTabMode] = useState<TabMode>("manual");
  const {
    output,
    exitCode,
    trace,
    errorType,
    suggestions,
    loading,
    apiError,
    history,
    currentPath,
    runCommand,
    navigateTo,
    clearApiError,
  } = useWikiFS();

  const [showStats, setShowStats] = useState(false);
  const [stats, setStats] = useState<Stats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [serverOnline, setServerOnline] = useState<boolean | null>(null);

  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const s = await fetchStats();
      setStats(s);
    } catch {
      setStats(null);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    checkHealth().then(setServerOnline);
    const id = setInterval(() => checkHealth().then(setServerOnline), 10000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    if (showStats) loadStats();
  }, [showStats, loadStats]);

  return (
    <div className="flex min-h-screen flex-col bg-slate-950">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-slate-700/60 bg-slate-900/90 px-5 py-3 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <span className="flex items-center justify-center w-8 h-8 rounded bg-blue-600/20 border border-blue-500/30 text-blue-400 font-mono text-sm font-bold select-none">
            &gt;_
          </span>
          <div>
            <h1 className="text-sm font-semibold text-slate-100 leading-none">WikiFS Explorer</h1>
            <p className="text-xs text-slate-500 mt-0.5">Wikipedia als virtuelles Dateisystem</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Tabs */}
          <div className="flex rounded-lg border border-slate-700/60 bg-slate-800/60 p-0.5">
            <button
              type="button"
              onClick={() => setTabMode("manual")}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                tabMode === "manual"
                  ? "bg-slate-700 text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              Manual
            </button>
            <button
              type="button"
              onClick={() => setTabMode("agent")}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                tabMode === "agent"
                  ? "bg-slate-700 text-slate-100"
                  : "text-slate-500 hover:text-slate-300"
              }`}
            >
              Agent
            </button>
          </div>
          {/* Server Status */}
          <div className="flex items-center gap-1.5">
            <span
              className={`w-2 h-2 rounded-full ${
                serverOnline === null
                  ? "bg-slate-500"
                  : serverOnline
                  ? "bg-green-500 shadow-[0_0_6px_rgba(34,197,94,0.6)]"
                  : "bg-red-500 shadow-[0_0_6px_rgba(239,68,68,0.6)]"
              }`}
            />
            <span className="text-xs text-slate-500">
              {serverOnline === null ? "Verbinden…" : serverOnline ? "Online" : "Offline"}
            </span>
          </div>
          <button
            type="button"
            onClick={() => setShowStats(true)}
            className="rounded-full border border-slate-600 bg-slate-800 px-3 py-1 text-xs text-slate-300 hover:bg-slate-700 hover:text-slate-100 transition-colors"
          >
            ◎ Stats
          </button>
        </div>
      </header>

      <main className="flex flex-1 flex-col gap-3 p-4">
        {/* Alerts */}
        {serverOnline === false && (
          <div className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-950/40 px-4 py-2.5 text-sm text-amber-300">
            <span className="text-amber-400">⚠</span>
            <span>
              WikiFS-Server nicht erreichbar — starten mit:{" "}
              <code className="font-mono text-amber-200 bg-amber-900/50 px-1.5 py-0.5 rounded text-xs">
                wikifs serve
              </code>
            </span>
          </div>
        )}

        {apiError && (
          <div className="flex items-center justify-between gap-2 rounded-lg border border-red-500/40 bg-red-950/40 px-4 py-2.5 text-sm text-red-300">
            <span className="flex items-center gap-2">
              <span className="text-red-400">✗</span>
              {apiError}
            </span>
            <button
              type="button"
              onClick={clearApiError}
              className="text-red-400 hover:text-red-200 transition-colors ml-2 text-xs"
            >
              Schließen ×
            </button>
          </div>
        )}

        {tabMode === "manual" ? (
          <>
            {/* Command Area */}
            <section className="rounded-lg border border-slate-700/60 bg-slate-900/60 p-3">
              <div className="mb-2">
                <Breadcrumb path={currentPath} onNavigate={navigateTo} />
              </div>
              <CommandInput onRun={runCommand} loading={loading} history={history} />
              <div className="mt-2">
                <QuickActions onRun={runCommand} loading={loading} />
              </div>
            </section>

            {/* Output + Trace */}
            <div className="grid flex-1 gap-3 md:grid-cols-2">
              <section className="flex flex-col">
                <h2 className="mb-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Output
                </h2>
                <OutputPanel
                  output={output}
                  exitCode={exitCode}
                  errorType={errorType}
                  suggestions={suggestions}
                  currentPath={currentPath}
                  onNavigate={navigateTo}
                />
              </section>
              <section className="flex flex-col">
                <h2 className="mb-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">
                  Trace Timeline
                </h2>
                <TraceTimeline trace={trace} />
              </section>
            </div>
          </>
        ) : (
          <AgentPanel />
        )}
      </main>

      {showStats && (
        <StatsView
          stats={stats}
          loading={statsLoading}
          onClose={() => setShowStats(false)}
        />
      )}
    </div>
  );
}

export default App;
