interface QuickActionsProps {
  onRun: (input: string) => void;
  loading: boolean;
}

const QUICK_ACTIONS = [
  { label: "ls /wiki/classes/", cmd: "ls /wiki/classes/" },
  { label: 'search "Berlin"', cmd: 'search "Berlin"' },
  { label: "ls /wiki/entities/", cmd: "ls /wiki/entities/" },
];

export function QuickActions({ onRun, loading }: QuickActionsProps) {
  return (
    <div className="flex flex-wrap gap-2">
      <span className="text-sm text-gray-500">Quick Actions:</span>
      {QUICK_ACTIONS.map(({ label, cmd }) => (
        <button
          key={cmd}
          type="button"
          onClick={() => onRun(cmd)}
          disabled={loading}
          className="rounded border border-gray-300 bg-white px-2 py-1 text-xs font-mono hover:bg-gray-50 disabled:opacity-50"
        >
          {label}
        </button>
      ))}
    </div>
  );
}
