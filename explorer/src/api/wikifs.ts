import type { CommandResponse, Stats } from "../types";

const API_BASE = "http://localhost:8000";

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
