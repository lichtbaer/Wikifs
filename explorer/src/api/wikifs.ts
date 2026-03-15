import type { CommandResponse, Stats } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function executeCommand(
  body: { command: string; path: string; flags?: string[]; pattern?: string | null },
  includeTrace = true
): Promise<CommandResponse> {
  const url = `${API_BASE}/execute${includeTrace ? "?include_trace=true" : ""}`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      command: body.command,
      path: body.path,
      flags: body.flags ?? [],
      pattern: body.pattern ?? null,
    }),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<CommandResponse>;
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<Stats>;
}

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/health`);
    return res.ok;
  } catch {
    return false;
  }
}

export type AgentStreamEventCallback = (event: string, data: Record<string, unknown>) => void;

/** Stream agent execution via POST /agent/stream. Calls callback for each SSE event. */
export async function agentStream(
  query: string,
  model: string | null,
  onEvent: AgentStreamEventCallback
): Promise<void> {
  const res = await fetch(`${API_BASE}/agent/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, model }),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";
    for (const block of lines) {
      let eventType = "message";
      let dataStr = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7).trim();
        } else if (line.startsWith("data: ")) {
          dataStr = line.slice(6);
        }
      }
      if (dataStr) {
        try {
          const data = JSON.parse(dataStr) as Record<string, unknown>;
          onEvent(eventType, data);
        } catch {
          // ignore parse errors
        }
      }
    }
  }
  if (buffer) {
    let eventType = "message";
    let dataStr = "";
    for (const line of buffer.split("\n")) {
      if (line.startsWith("event: ")) eventType = line.slice(7).trim();
      else if (line.startsWith("data: ")) dataStr = line.slice(6);
    }
    if (dataStr) {
      try {
        const data = JSON.parse(dataStr) as Record<string, unknown>;
        onEvent(eventType, data);
      } catch {
        // ignore
      }
    }
  }
}
