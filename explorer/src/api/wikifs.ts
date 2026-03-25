import type { CommandResponse, Stats } from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

const API_KEY_HEADERS: Record<string, string> = {};
{
  const k = import.meta.env.VITE_WIKIFS_API_KEY?.trim();
  if (k) API_KEY_HEADERS["X-API-Key"] = k;
}

function jsonHeaders(): HeadersInit {
  return { "Content-Type": "application/json", ...API_KEY_HEADERS };
}

export async function executeCommand(
  body: {
    command: string;
    path: string;
    flags?: string[];
    pattern?: string | null;
    lang?: string;
  },
  includeTrace = true
): Promise<CommandResponse> {
  const url = `${API_BASE}/execute${includeTrace ? "?include_trace=true" : ""}`;
  const payload: Record<string, unknown> = {
    command: body.command,
    path: body.path,
    flags: body.flags ?? [],
    pattern: body.pattern ?? null,
  };
  if (body.lang?.trim()) {
    payload.lang = body.lang.trim().toLowerCase();
  }
  const res = await fetch(url, {
    method: "POST",
    headers: jsonHeaders(),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  }
  return res.json() as Promise<CommandResponse>;
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_BASE}/stats`, { headers: API_KEY_HEADERS });
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

export interface TraceListItem {
  trace_id: string;
  command: string;
  path: string;
  total_duration_ms: number;
  exit_code: number;
  timestamp: string;
}

export interface ErrorListItem {
  error_id: string;
  timestamp: string;
  category: string;
  severity: string;
  message: string;
  resolved: boolean;
}

export async function fetchTraces(limit = 25): Promise<TraceListItem[]> {
  const res = await fetch(`${API_BASE}/traces?limit=${limit}`, {
    headers: API_KEY_HEADERS,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = (await res.json()) as Array<{
    trace_id: string;
    command: string;
    path: string;
    total_duration_ms: number;
    exit_code: number;
    timestamp: string;
  }>;
  return data.map((t) => ({
    trace_id: t.trace_id,
    command: t.command,
    path: t.path,
    total_duration_ms: t.total_duration_ms,
    exit_code: t.exit_code,
    timestamp: t.timestamp,
  }));
}

export async function fetchErrors(limit = 25): Promise<ErrorListItem[]> {
  const res = await fetch(`${API_BASE}/errors?limit=${limit}`, {
    headers: API_KEY_HEADERS,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = (await res.json()) as Array<{
    error_id: string;
    timestamp: string;
    category: string;
    severity: string;
    message: string;
    resolved: boolean;
  }>;
  return data.map((e) => ({
    error_id: e.error_id,
    timestamp: e.timestamp,
    category: e.category,
    severity: e.severity,
    message: e.message,
    resolved: e.resolved,
  }));
}

export async function clearServerCache(): Promise<number> {
  const res = await fetch(`${API_BASE}/cache`, {
    method: "DELETE",
    headers: API_KEY_HEADERS,
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = (await res.json()) as { deleted: number };
  return data.deleted;
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
    headers: jsonHeaders(),
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
