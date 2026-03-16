import { useState, useCallback } from "react";
import { ExampleQuestions } from "./ExampleQuestions";

interface AgentInputProps {
  onAsk: (query: string, model?: string | null) => void;
  loading: boolean;
}

const MODELS = [
  { value: "openai:gpt-4.1", label: "GPT-4.1" },
  { value: "anthropic:claude-sonnet-4-6", label: "Claude Sonnet 4.6" },
];

export function AgentInput({ onAsk, loading }: AgentInputProps) {
  const [query, setQuery] = useState("");
  const [model, setModel] = useState("openai:gpt-4.1");

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = query.trim();
      if (trimmed && !loading) {
        onAsk(trimmed, model);
      }
    },
    [query, model, loading, onAsk]
  );

  const handleExampleClick = useCallback((q: string) => {
    setQuery(q);
  }, []);

  return (
    <div className="space-y-2">
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-2">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Stelle eine Frage an den Agenten…"
          rows={2}
          className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder-slate-600 focus:border-blue-500/60 focus:outline-none transition-colors resize-none"
          disabled={loading}
          autoComplete="off"
        />
        <div className="flex gap-2 shrink-0">
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={loading}
            className="rounded border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-200 focus:border-blue-500/60 focus:outline-none"
          >
            {MODELS.map((m) => (
              <option key={m.value} value={m.value}>
                {m.label}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40 transition-colors"
          >
            {loading ? (
              <>
                <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin align-middle mr-1.5" />
                Läuft…
              </>
            ) : (
              "Ask"
            )}
          </button>
        </div>
      </form>
      <ExampleQuestions onSelect={handleExampleClick} disabled={loading} />
    </div>
  );
}
