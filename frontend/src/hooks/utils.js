// ─────────────────────────────────────────────────────────────
// Formatting helpers
// ─────────────────────────────────────────────────────────────
import { useState, useCallback, useRef, useEffect } from "react";

export function fmtDate(d) {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function fmtTime(dt) {
  if (!dt) return "—";
  return new Date(dt).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtHours(h) {
  if (h == null) return "—";
  const n = parseFloat(h);
  const hrs = Math.floor(n);
  const mins = Math.round((n - hrs) * 60);
  return mins ? `${hrs}h ${mins}m` : `${hrs}h`;
}

// Flatten DRF error shapes into a single human-readable string
export function errorMsg(e) {
  if (!e) return "Unknown error";
  if (e.data) {
    const msgs = Object.values(e.data).flat().join(" ");
    return msgs || JSON.stringify(e.data);
  }
  return String(e);
}

// ─────────────────────────────────────────────────────────────
// useAsync — wraps any async function with loading / error state
//
// Usage: pass a useCallback-stabilised function as `fn`, or pass
// a plain inline function when the identity changing on every
// render is intentional (the hook will re-create `run` each time,
// which is fine — the state machine itself is stable).
// ─────────────────────────────────────────────────────────────
export function useAsync(fn) {
  const [state, setState] = useState({
    loading: false,
    data: null,
    error: null,
  });

  // Store fn in a ref so `run` never needs fn in its dep array.
  // This avoids the exhaustive-deps warning while still always
  // calling the latest version of fn.
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });

  const run = useCallback(async (...args) => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fnRef.current(...args);
      setState({ loading: false, data, error: null });
      return data;
    } catch (e) {
      setState({ loading: false, data: null, error: e });
      throw e;
    }
  }, []); // run is created once; always calls the latest fn via ref

  return { ...state, run };
}
