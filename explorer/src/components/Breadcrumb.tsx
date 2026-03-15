interface BreadcrumbProps {
  path: string;
  onNavigate: (path: string) => void;
}

function splitPath(path: string): string[] {
  const normalized = path.replace(/\/$/, "") || "/";
  const parts = normalized.split("/").filter(Boolean);
  return parts;
}

export function Breadcrumb({ path, onNavigate }: BreadcrumbProps) {
  const parts = splitPath(path);

  const segments: { label: string; fullPath: string }[] = [];
  let acc = "";
  for (const p of parts) {
    acc = acc ? acc + "/" + p : "/" + p;
    segments.push({ label: p, fullPath: acc });
  }

  return (
    <div className="flex flex-wrap items-center gap-0.5 text-xs font-mono">
      <button
        type="button"
        onClick={() => onNavigate("/wiki/")}
        className="text-blue-400 hover:text-blue-300 transition-colors"
      >
        ~
      </button>
      {segments.map((s, idx) => (
        <span key={s.fullPath} className="flex items-center">
          <span className="text-slate-600 mx-0.5">/</span>
          <button
            type="button"
            onClick={() => onNavigate(s.fullPath + (s.label.includes(".") ? "" : "/"))}
            className={`transition-colors ${
              idx === segments.length - 1
                ? "text-slate-200"
                : "text-blue-400 hover:text-blue-300"
            }`}
          >
            {s.label}
          </button>
        </span>
      ))}
      {segments.length > 0 && (
        <button
          type="button"
          onClick={() => {
            const parent = segments.length > 1 ? segments[segments.length - 2]!.fullPath : "/wiki/";
            onNavigate(parent + "/");
          }}
          className="ml-2 text-slate-500 hover:text-slate-300 transition-colors"
          title="Zurück"
        >
          ←
        </button>
      )}
    </div>
  );
}
