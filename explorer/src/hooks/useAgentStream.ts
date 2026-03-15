import { useCallback, useState } from "react";
import { agentStream } from "../api/wikifs";
import type { AgentAnswerSummary, AgentStep } from "../types";

export function useAgentStream() {
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [answer, setAnswer] = useState<AgentAnswerSummary | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const askAgent = useCallback(async (query: string, model?: string | null) => {
    setIsRunning(true);
    setSteps([]);
    setAnswer(null);
    setError(null);

    const stepsMap = new Map<number, AgentStep>();

    const onEvent = (event: string, data: Record<string, unknown>) => {
      if (event === "tool_call") {
        const step = data.step as number;
        const cmd = (data.command as string) ?? "?";
        const path = (data.path as string) ?? "";
        const pattern = (data.pattern as string | null) ?? null;
        stepsMap.set(step, {
          step,
          command: cmd,
          path,
          pattern,
          status: "running",
        });
        setSteps(Array.from(stepsMap.values()).sort((a, b) => a.step - b.step));
      } else if (event === "tool_result") {
        const step = data.step as number;
        const existing = stepsMap.get(step);
        if (existing) {
          existing.status = (data.exit_code as number) === 0 ? "done" : "error";
          existing.output = (data.output as string) ?? null;
          existing.exit_code = data.exit_code as number;
          existing.timing_ms = data.timing_ms as number;
          existing.trace = (data.trace as AgentStep["trace"]) ?? null;
          if (existing.status === "error") {
            existing.error = (data.output as string) ?? "Unknown error";
          }
        } else {
          stepsMap.set(step, {
            step,
            command: "?",
            path: "",
            status: "done",
            output: (data.output as string) ?? null,
            exit_code: data.exit_code as number,
            timing_ms: data.timing_ms as number,
            trace: (data.trace as AgentStep["trace"]) ?? null,
          });
        }
        setSteps(Array.from(stepsMap.values()).sort((a, b) => a.step - b.step));
      } else if (event === "answer") {
        setAnswer({
          answer: (data.answer as string) ?? "",
          total_commands: (data.total_commands as number) ?? 0,
          total_duration_ms: (data.total_duration_ms as number) ?? 0,
          cache_hits: (data.cache_hits as number) ?? 0,
        });
      } else if (event === "error") {
        const step = data.step as number;
        const msg = (data.message as string) ?? "Unknown error";
        const existing = stepsMap.get(step);
        if (existing) {
          existing.status = "error";
          existing.error = msg;
        } else {
          stepsMap.set(step, {
            step,
            command: "?",
            path: "",
            status: "error",
            error: msg,
          });
        }
        setSteps(Array.from(stepsMap.values()).sort((a, b) => a.step - b.step));
        setError(msg);
      }
    };

    try {
      await agentStream(query, model ?? null, onEvent);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(
        msg.includes("fetch") || msg.includes("Failed")
          ? "WikiFS-Server nicht erreichbar. Starten mit: wikifs serve"
          : msg
      );
    } finally {
      setIsRunning(false);
    }
  }, []);

  const reset = useCallback(() => {
    setSteps([]);
    setAnswer(null);
    setError(null);
  }, []);

  return { steps, answer, isRunning, error, askAgent, reset };
}
