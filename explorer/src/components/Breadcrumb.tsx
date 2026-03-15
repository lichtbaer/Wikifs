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
  if (parts.length === 0) {
    return (
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onNavigate("/wiki/")}
          className="text-sm text-blue-600 hover:underline"
        >
          /wiki
        </button>
      </div>
    );
  }

  const segments: { label: string; fullPath: string }[] = [];
  let acc = "";
  for (const p of parts) {
    acc = acc ? acc + "/" + p : "/" + p;
    segments.push({ label: p, fullPath: acc });
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => onNavigate("/wiki/")}
        className="text-sm text-blue-600 hover:underline"
      >
        /wiki
      </button>
      {segments.map((s) => (
        <span key={s.fullPath} className="flex items-center gap-2">
          <span className="text-gray-400">/</span>
          <button
            type="button"
            onClick={() => onNavigate(s.fullPath + (s.label.includes(".") ? "" : "/"))}
            className="text-sm text-blue-600 hover:underline"
          >
            {s.label}
          </button>
        </span>
      ))}
      <div className="ml-2">
        <button
          type="button"
          onClick={() => {
            const parent = segments.length > 1 ? segments[segments.length - 2]!.fullPath : "/wiki/";
            onNavigate(parent + "/");
          }}
          className="rounded border border-gray-300 bg-white px-2 py-1 text-xs hover:bg-gray-50"
        >
          ← Back
        </button>
      </div>
    </div>
  );
}
