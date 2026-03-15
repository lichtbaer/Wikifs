import { useState, useCallback, useEffect } from "react";
import { useWikiFS } from "./hooks/useWikiFS";
import { fetchStats, checkHealth } from "./api/wikifs";
import { CommandInput } from "./components/CommandInput";
import { QuickActions } from "./components/QuickActions";
import { OutputPanel } from "./components/OutputPanel";
import { TraceTimeline } from "./components/TraceTimeline";
import { Breadcrumb } from "./components/Breadcrumb";
import { StatsView } from "./components/StatsView";
import type { Stats } from "./types";

function App() {
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
    <div className="flex min-h-screen flex-col bg-gray-100">
      <header className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3">
        <h1 className="text-lg font-semibold">WikiFS Explorer</h1>
        <button
          type="button"
          onClick={() => setShowStats(true)}
          className="rounded border border-gray-300 bg-white px-3 py-1 text-sm hover:bg-gray-50"
        >
          Stats
        </button>
      </header>

      <main className="flex flex-1 flex-col gap-4 p-4">
        {serverOnline === false && (
          <div className="rounded border border-amber-500 bg-amber-50 px-4 py-2 text-sm text-amber-800">
            WikiFS-Server nicht erreichbar. Starten mit: <code className="font-mono">wikifs serve</code>
          </div>
        )}

        {apiError && (
          <div className="rounded border border-red-500 bg-red-50 px-4 py-2 text-sm text-red-800">
            {apiError}
            <button
              type="button"
              onClick={clearApiError}
              className="ml-2 text-red-600 hover:underline"
            >
              Schließen
            </button>
          </div>
        )}

        <section>
          <label className="mb-2 block text-sm font-medium text-gray-700">
            Command Input
          </label>
          <CommandInput onRun={runCommand} loading={loading} history={history} />
        </section>

        <QuickActions onRun={runCommand} loading={loading} />

        <div className="grid flex-1 gap-4 md:grid-cols-2">
          <section className="flex flex-col">
            <h2 className="mb-2 text-sm font-medium text-gray-700">Output</h2>
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
            <h2 className="mb-2 text-sm font-medium text-gray-700">Trace Timeline</h2>
            <TraceTimeline trace={trace} />
          </section>
        </div>

        <section className="rounded border border-gray-200 bg-white p-4">
          <h2 className="mb-2 text-sm font-medium text-gray-700">Navigation Breadcrumb</h2>
          <Breadcrumb path={currentPath} onNavigate={navigateTo} />
        </section>
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
