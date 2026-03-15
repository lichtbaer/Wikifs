/** CommandResponse from POST /execute */
export interface CommandResponse {
  output: string;
  exit_code: number;
  request_id: string;
  trace_id: string;
  timing_ms: number;
  error_type?: string | null;
  suggestions?: string[] | null;
  trace?: Trace | null;
}

/** Trace phase from trace.phases */
export interface TracePhase {
  phase: string;
  duration_ms: number;
  result: string;
  cache_hit?: boolean | null;
  api_url?: string | null;
  response_bytes?: number | null;
  error?: string | null;
  metadata?: Record<string, unknown> | null;
}

/** Full trace object */
export interface Trace {
  trace_id: string;
  request_id: string;
  timestamp: string;
  command: string;
  path: string;
  flags: string[];
  phases: TracePhase[];
  total_duration_ms: number;
  cache_hits: number;
  cache_misses: number;
  api_calls: number;
  response_bytes: number;
  exit_code: number;
}

/** Stats from GET /stats */
export interface Stats {
  count: number;
  avg_duration_ms: number;
  p50_duration_ms: number;
  p95_duration_ms: number;
  max_duration_ms: number;
  cache_hit_rate: number;
  commands_by_type: Record<string, number>;
}

/** Parsed command for API */
export interface ApiCommand {
  command: "ls" | "cat" | "grep" | "search";
  path: string;
  flags: string[];
  pattern?: string | null;
}
