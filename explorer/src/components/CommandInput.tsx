import { useState, useCallback, useRef, useEffect } from "react";

interface CommandInputProps {
  onRun: (input: string) => void;
  loading: boolean;
  history: string[];
}

export function CommandInput({ onRun, loading, history }: CommandInputProps) {
  const [input, setInput] = useState("");
  const [historyIndex, setHistoryIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const trimmed = input.trim();
      if (trimmed && !loading) {
        onRun(trimmed);
        setInput("");
        setHistoryIndex(-1);
      }
    },
    [input, loading, onRun]
  );

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "ArrowUp" && e.key !== "ArrowDown") return;
      if (document.activeElement !== inputRef.current) return;
      e.preventDefault();
      if (history.length === 0) return;
      let next = historyIndex;
      if (e.key === "ArrowUp") {
        next = historyIndex < history.length - 1 ? historyIndex + 1 : history.length - 1;
      } else {
        next = historyIndex <= 0 ? -1 : historyIndex - 1;
      }
      setHistoryIndex(next);
      setInput(next >= 0 ? history[next] ?? "" : "");
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [history, historyIndex]);

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-2">
      <span className="select-none font-mono text-green-400 text-sm shrink-0">$</span>
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="ls /wiki/entities/Frankfurt_am_Main/"
        className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm text-slate-100 placeholder-slate-600 caret-green-400 focus:border-blue-500/60 focus:outline-none terminal-glow transition-colors"
        disabled={loading}
        autoComplete="off"
        spellCheck={false}
      />
      <button
        type="submit"
        disabled={loading}
        className="flex items-center gap-1.5 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-40 transition-colors shrink-0"
      >
        {loading ? (
          <>
            <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            <span>Läuft…</span>
          </>
        ) : (
          <>
            <span>▶</span>
            <span>Run</span>
          </>
        )}
      </button>
    </form>
  );
}
