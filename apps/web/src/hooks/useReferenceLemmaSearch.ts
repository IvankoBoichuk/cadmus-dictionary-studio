import { useCallback, useEffect, useRef, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type ReferenceLemmaResponse,
} from "../api";

const DEBOUNCE_MS = 300;
const RESULT_LIMIT = 20;

export type ReferenceLemmaSearchState =
  | { status: "idle" }
  | { status: "searching" }
  | { status: "results"; results: ReferenceLemmaResponse[] }
  | { status: "error"; message: string };

/**
 * Debounced lookup of a reference lexicon (VESUM by default). Mirrors
 * `useSettlementSearch`: a plain `setTimeout` debounce plus an
 * `AbortController` so a stale request can't overwrite a newer one.
 * `standardOnly` toggles the literary-standard filter the API applies
 * (ADR-0009); a blank query keeps the hook idle.
 */
export function useReferenceLemmaSearch(code: string) {
  const [query, setQuery] = useState("");
  const [standardOnly, setStandardOnly] = useState(true);
  const [state, setState] = useState<ReferenceLemmaSearchState>({ status: "idle" });
  const controllerRef = useRef<AbortController | null>(null);

  const tick = useCallback(
    (currentQuery: string, currentStandardOnly: boolean) => {
      const trimmed = currentQuery.trim();
      controllerRef.current?.abort();
      if (trimmed.length === 0) {
        setState({ status: "idle" });
        return;
      }
      const controller = new AbortController();
      controllerRef.current = controller;
      setState({ status: "searching" });
      API.referenceLexicons
        .searchLemmas(
          code,
          {
            query: trimmed,
            standardOnly: currentStandardOnly,
            limit: RESULT_LIMIT,
          },
          { signal: controller.signal },
        )
        .then(
          (results) => setState({ status: "results", results }),
          (error: unknown) => {
            if (isAbortError(error)) return;
            setState({
              status: "error",
              message:
                apiMessageFrom(error) ??
                "Не вдалося виконати пошук у довідковому словнику.",
            });
          },
        );
    },
    [code],
  );

  useEffect(() => {
    const timeoutId = window.setTimeout(
      () => tick(query, standardOnly),
      DEBOUNCE_MS,
    );
    return () => window.clearTimeout(timeoutId);
  }, [tick, query, standardOnly]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  return { query, setQuery, standardOnly, setStandardOnly, state } as const;
}
