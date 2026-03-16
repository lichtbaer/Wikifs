import { useAgentStream } from "../hooks/useAgentStream";
import { AgentInput } from "./AgentInput";
import { AgentSteps } from "./AgentSteps";
import { AgentAnswer } from "./AgentAnswer";

export function AgentPanel() {
  const { steps, answer, isRunning, error, askAgent } = useAgentStream();

  return (
    <div className="flex flex-col h-full gap-4">
      <section className="rounded-lg border border-slate-700/60 bg-slate-900/60 p-3">
        <h2 className="mb-2 text-xs font-medium text-slate-500 uppercase tracking-wider">
          Ask the Agent
        </h2>
        <AgentInput onAsk={askAgent} loading={isRunning} />
      </section>

      {error && (
        <div className="rounded-lg border border-red-500/40 bg-red-950/40 px-4 py-2.5 text-sm text-red-300">
          <span className="text-red-400">✗</span> {error}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2 flex-1 min-h-0">
        <section className="flex flex-col h-full">
          <h2 className="mb-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">
            Agent Steps
          </h2>
          <AgentSteps steps={steps} isRunning={isRunning} />
        </section>
        <section className="flex flex-col h-full">
          <h2 className="mb-1.5 text-xs font-medium text-slate-500 uppercase tracking-wider">
            Agent Answer
          </h2>
          <AgentAnswer summary={answer} />
        </section>
      </div>
    </div>
  );
}
