import { useCallback, useReducer, useState } from "react";
import { executeCommand } from "../api/wikifs";
import type { CommandResponse } from "../types";
import { parseCommandString } from "../utils/parseCommand";

type State = {
  output: string;
  exitCode: number | null;
  trace: CommandResponse["trace"];
  errorType: string | null;
  suggestions: string[] | null;
  loading: boolean;
  apiError: string | null;
  history: string[];
  currentPath: string;
};

type Action =
  | { type: "EXECUTE_START" }
  | { type: "EXECUTE_SUCCESS"; payload: CommandResponse }
  | { type: "EXECUTE_ERROR"; payload: string }
  | { type: "SET_PATH"; payload: string }
  | { type: "NAVIGATE"; payload: string }
  | { type: "CLEAR_API_ERROR" }
  | { type: "ADD_HISTORY"; payload: string };

const initialState: State = {
  output: "",
  exitCode: null,
  trace: null,
  errorType: null,
  suggestions: null,
  loading: false,
  apiError: null,
  history: [],
  currentPath: "/wiki/",
};

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "EXECUTE_START":
      return { ...state, loading: true, apiError: null };
    case "EXECUTE_SUCCESS": {
      const r = action.payload;
      return {
        ...state,
        output: r.output,
        exitCode: r.exit_code,
        trace: r.trace ?? null,
        errorType: r.error_type ?? null,
        suggestions: r.suggestions ?? null,
        loading: false,
        apiError: null,
        history: state.history,
        currentPath: r.trace?.path ?? state.currentPath,
      };
    }
    case "EXECUTE_ERROR":
      return {
        ...state,
        loading: false,
        apiError: action.payload,
        output: "",
        exitCode: null,
        trace: null,
      };
    case "SET_PATH":
      return { ...state, currentPath: action.payload };
    case "NAVIGATE":
      return { ...state, currentPath: action.payload };
    case "CLEAR_API_ERROR":
      return { ...state, apiError: null };
    case "ADD_HISTORY": {
      const cmd = action.payload;
      const prev = state.history.filter((h) => h !== cmd);
      return { ...state, history: [cmd, ...prev].slice(0, 50) };
    }
    default:
      return state;
  }
}

export function useWikiFS() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const [requestLang, setRequestLang] = useState("");

  const runCommand = useCallback(async (input: string) => {
    const trimmed = input.trim();
    if (trimmed) {
      dispatch({ type: "ADD_HISTORY", payload: trimmed });
    }
    const parsed = parseCommandString(input);
    if ("error" in parsed) {
      dispatch({
        type: "EXECUTE_SUCCESS",
        payload: {
          output: parsed.error,
          exit_code: 1,
          request_id: "",
          trace_id: "",
          timing_ms: 0,
          error_type: "parse_error",
        },
      });
      return;
    }

    dispatch({ type: "EXECUTE_START" });
    try {
      const response = await executeCommand(
        {
          command: parsed.command,
          path: parsed.path,
          flags: parsed.flags,
          pattern: parsed.pattern,
          ...(requestLang.trim() ? { lang: requestLang.trim() } : {}),
        },
        true
      );
      dispatch({ type: "EXECUTE_SUCCESS", payload: response });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      dispatch({
        type: "EXECUTE_ERROR",
        payload: msg.includes("fetch") || msg.includes("Failed")
          ? "WikiFS-Server nicht erreichbar. Starten mit: wikifs serve"
          : msg,
      });
    }
  }, [requestLang]);

  const navigateTo = useCallback((path: string) => {
    dispatch({ type: "NAVIGATE", payload: path });
    const isDir = path.endsWith("/") || !path.includes(".");
    runCommand(isDir ? `ls ${path}` : `cat ${path}`);
  }, [runCommand]);

  const setPath = useCallback((path: string) => {
    dispatch({ type: "SET_PATH", payload: path });
  }, []);

  const clearApiError = useCallback(() => {
    dispatch({ type: "CLEAR_API_ERROR" });
  }, []);

  return {
    ...state,
    runCommand,
    navigateTo,
    setPath,
    clearApiError,
    requestLang,
    setRequestLang,
  };
}
