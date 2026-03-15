interface QuickActionsProps {
  onRun: (input: string) => void;
  loading: boolean;
}

const QUICK_ACTIONS = [
  { label: "ls classes/", cmd: "ls /wiki/classes/", icon: "📂" },
  { label: 'search "Berlin"', cmd: 'search "Berlin"', icon: "🔍" },
  { label: "ls entities/", cmd: "ls /wiki/entities/", icon: "📂" },
];

export function QuickActions({ onRun, loading }: QuickActionsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-slate-500 shrink-0">⚡ Schnellzugriff:</span>
      {QUICK_ACTIONS.map(({ label, cmd, icon }) => (
        <button
          key={cmd}
          type="button"
          onClick={() => onRun(cmd)}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-full border border-slate-600 bg-slate-800 px-3 py-1 font-mono text-xs text-slate-300 hover:bg-slate-700 hover:text-slate-100 hover:border-slate-500 disabled:opacity-40 transition-colors"
        >
          <span>{icon}</span>
          <span>{label}</span>
        </button>
      ))}
    </div>
  );
}
