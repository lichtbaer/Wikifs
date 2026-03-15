import { useState } from "react";
import type { AgentStep } from "../types";
import { TraceTimeline } from "./TraceTimeline";

interface AgentStepCardProps {
  step: AgentStep;
}

function commandIcon(cmd: string): string {
  const c = cmd.toLowerCase();
  if (c === "search") return "🔍";
  if (c === "ls") return "📁";
  if (c === "cat") return "📄";
  if (c === "grep") return "🔎";
  return "▸";
}

function commandLabel(step: AgentStep): string {
  const { command, path, pattern } = step;
  if (command === "search" && pattern) {
    return `search "${pattern}"`;
  }
  if (command === "grep" && pattern) {
    return `grep "${pattern}" ${path}`;
  }
  return `${command} ${path}`.trim();
}

export function AgentStepCard({ step }: AgentStepCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isRunning = step.status === "running";
  const isError = step.status === "error";

  return (
    <div
      className={`rounded-lg border p-3 transition-colors ${
        isError
          ? "border-red-500/50 bg-red-950/30"
          : "border-slate-700/60 bg-slate-900/60"
      }`}
    >
      <div className="flex items-start gap-2">
        <span className="text-lg shrink-0">{commandIcon(step.command)}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-sm text-slate-200">
              {commandLabel(step)}
            </span>
            {isRunning && (
              <span className="inline-flex items-center gap-1 text-xs text-slate-500">
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                Running…
              </span>
            )}
            {step.status === "done" && step.timing_ms != null && (
              <span className="text-xs text-slate-500 font-mono">
                {Math.round(step.timing_ms)}ms
              </span>
            )}
          </div>
          {step.output != null && step.output !== "" && (
            <div className="mt-2">
              <button
                type="button"
                onClick={() => setExpanded(!expanded)}
                className="text-xs text-slate-500 hover:text-slate-400 transition-colors"
              >
                {expanded ? "▼ Output ausblenden" : "▶ Output anzeigen"}
              </button>
              {expanded && (
                <pre className="mt-1 p-2 rounded bg-slate-950/80 text-xs text-slate-300 overflow-x-auto max-h-48 overflow-y-auto whitespace-pre-wrap break-words">
                  {step.output}
                </pre>
              )}
            </div>
          )}
          {step.error && (
            <p className="mt-1 text-sm text-red-400">{step.error}</p>
          )}
        </div>
      </div>
      {step.trace && step.status === "done" && (
        <div className="mt-3 pt-3 border-t border-slate-700/60">
          <span className="text-xs text-slate-500 uppercase tracking-wider">
            Trace
          </span>
          <TraceTimeline trace={step.trace} />
        </div>
      )}
    </div>
  );
}
