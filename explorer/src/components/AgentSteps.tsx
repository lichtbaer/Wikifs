import type { AgentStep } from "../types";
import { AgentStepCard } from "./AgentStepCard";

interface AgentStepsProps {
  steps: AgentStep[];
  isRunning: boolean;
}

export function AgentSteps({ steps, isRunning }: AgentStepsProps) {
  if (steps.length === 0 && !isRunning) {
    return (
      <div className="flex-1 rounded-lg border border-slate-700/60 bg-slate-900/60 p-6 text-center">
        <p className="text-sm text-slate-500">
          Keine Schritte. Stelle eine Frage an den Agenten.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 space-y-2 overflow-y-auto">
      {steps.map((step) => (
        <AgentStepCard key={step.step} step={step} />
      ))}
      {isRunning && steps.length > 0 && steps[steps.length - 1]?.status === "running" && (
        <div className="rounded-lg border border-slate-700/60 bg-slate-900/40 p-2">
          <span className="text-xs text-slate-500">⏳ Warte auf Ergebnis…</span>
        </div>
      )}
    </div>
  );
}
