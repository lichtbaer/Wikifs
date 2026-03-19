import type { ApiCommand } from "../types";

/**
 * Parse user command string (e.g. "ls /wiki/classes/") into API format.
 * Auto-detects command type: ls, cat, head, tail, grep, search.
 */
export function parseCommandString(input: string): ApiCommand | { error: string } {
  const trimmed = input.trim();
  if (!trimmed) {
    return { error: "Bitte einen Befehl eingeben." };
  }

  const parts = trimmed.split(/\s+/);
  const first = parts[0]?.toLowerCase();

  if (first === "ls") {
    const path = parts[1] ?? "/wiki/";
    return { command: "ls", path: normalizePath(path), flags: [] };
  }

  if (first === "cat") {
    const path = parts[1];
    if (!path) return { error: "cat benötigt einen Pfad." };
    return { command: "cat", path: normalizePath(path), flags: [] };
  }

  if (first === "head" || first === "tail") {
    const { flags, path, error } = parseHeadTailArgs(parts, first);
    if (error) return { error };
    if (!path) return { error: `${first} benötigt einen Pfad.` };
    return {
      command: first,
      path: normalizePath(path),
      flags,
    };
  }

  if (first === "grep") {
    const pattern = parts[1];
    const path = parts[2];
    if (!pattern || !path) return { error: "grep benötigt Muster und Pfad: grep <muster> <pfad>" };
    return { command: "grep", path: normalizePath(path), flags: [], pattern };
  }

  if (first === "search") {
    const rest = trimmed.slice(7).trim();
    const match = rest.match(/^["'](.+)["']$/);
    const query = match ? match[1] : rest;
    if (!query) return { error: "search benötigt eine Suchanfrage." };
    return {
      command: "search",
      path: "/wiki/search",
      flags: ["--type", "entity"],
      pattern: query,
    };
  }

  // Heuristic: if it looks like a path, assume ls
  if (trimmed.startsWith("/") || trimmed.startsWith("wiki/")) {
    return { command: "ls", path: normalizePath(trimmed), flags: [] };
  }

  return {
    error: `Unbekannter Befehl: ${first}. Erlaubt: ls, cat, head, tail, grep, search`,
  };
}

function parseHeadTailArgs(
  parts: string[],
  cmd: "head" | "tail"
): { flags: string[]; path: string; error?: string } {
  const flags: string[] = [];
  let i = 1;
  while (i < parts.length) {
    const p = parts[i]!;
    if (p === "-n" || p === "--lines") {
      const v = parts[i + 1];
      if (!v) {
        return { flags, path: "", error: `${cmd}: Wert nach ${p} fehlt.` };
      }
      if (!/^\d+$/.test(v)) {
        return { flags, path: "", error: `${cmd}: Ungültige Zeilenzahl: ${v}` };
      }
      flags.push(p, v);
      i += 2;
      continue;
    }
    if (p.startsWith("-")) {
      return { flags, path: "", error: `${cmd}: Unbekannte Option ${p}` };
    }
    break;
  }
  const path = parts.slice(i).join(" ");
  return { flags, path };
}

function normalizePath(p: string): string {
  let path = p.trim();
  if (!path.startsWith("/")) path = "/" + path;
  if (!path.startsWith("/wiki")) path = "/wiki" + (path === "/" ? "" : path);
  return path;
}
