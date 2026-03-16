import ReactMarkdown from "react-markdown";
import type { AgentAnswerSummary } from "../types";

interface AgentAnswerProps {
  summary: AgentAnswerSummary | null;
}

export function AgentAnswer({ summary }: AgentAnswerProps) {
  if (!summary) {
    return (
      <div className="flex-1 rounded-lg border border-slate-700/60 bg-slate-900/60 p-6">
        <p className="text-sm text-slate-500">
          Die Antwort des Agenten erscheint hier.
        </p>
      </div>
    );
  }

  const { answer, total_commands, total_duration_ms, cache_hits = 0 } = summary;

  return (
    <div className="flex flex-col flex-1 min-h-0 gap-3">
      <div className="flex-1 min-h-0 rounded-lg border border-slate-700/60 bg-slate-900/60 p-4 overflow-y-auto">
        <h3 className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-2">
          Agent-Antwort
        </h3>
        <div className="prose prose-invert prose-sm max-w-none text-slate-200">
          <ReactMarkdown>{answer}</ReactMarkdown>
        </div>
      </div>
      <div className="flex flex-wrap gap-4 text-xs text-slate-500">
        <span>
          <strong className="text-slate-400">{total_commands}</strong> Befehle
        </span>
        <span>
          <strong className="text-slate-400">{Math.round(total_duration_ms / 100) / 10}s</strong> Gesamt
        </span>
        {cache_hits > 0 && (
          <span>
            <strong className="text-green-400">{cache_hits}</strong> Cache-Hits
          </span>
        )}
      </div>
    </div>
  );
}
