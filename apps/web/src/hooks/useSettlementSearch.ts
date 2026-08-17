import { useCallback, useEffect, useRef, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type SettlementSearchFilters,
  type SettlementSuggestionResponse,
} from "../api";

const DEBOUNCE_MS = 300;

export type SettlementSearchState =
  | { status: "idle" }
  | { status: "searching" }
  | { status: "results"; results: SettlementSuggestionResponse[] }
  | { status: "error"; message: string };

function hasAnyFilter(filters: SettlementSearchFilters): boolean {
  return Boolean(
    filters.query?.trim() ||
      filters.areaId ||
      filters.regionId ||
      filters.communityId ||
      filters.category,
  );
}

/**
 * AC8: debounced search of the local settlement cache, so the search
 * combobox doesn't fire a request on every keystroke or filter change.
 * No debounce/autocomplete library exists in this repo, so this is a
 * plain `setTimeout` debounce with an `AbortController` to cancel a
 * still-in-flight request when a newer one supersedes it.
 */
export function useSettlementSearch(dictionaryId: string) {
  const [filters, setFilters] = useState<SettlementSearchFilters>({});
  const [state, setState] = useState<SettlementSearchState>({ status: "idle" });
  const controllerRef = useRef<AbortController | null>(null);

  const tick = useCallback(
    (currentFilters: SettlementSearchFilters) => {
      if (!hasAnyFilter(currentFilters)) {
        controllerRef.current?.abort();
        setState({ status: "idle" });
        return;
      }
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      setState({ status: "searching" });
      API.settlements
        .search(dictionaryId, currentFilters, { signal: controller.signal })
        .then(
          (results) => setState({ status: "results", results }),
          (error: unknown) => {
            if (isAbortError(error)) return;
            setState({
              status: "error",
              message: apiMessageFrom(error) ?? "Не вдалося виконати пошук.",
            });
          },
        );
    },
    [dictionaryId],
  );

  useEffect(() => {
    const timeoutId = window.setTimeout(() => tick(filters), DEBOUNCE_MS);
    return () => window.clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    tick,
    filters.query,
    filters.areaId,
    filters.regionId,
    filters.communityId,
    filters.category,
  ]);

  useEffect(() => () => controllerRef.current?.abort(), []);

  return { filters, setFilters, state } as const;
}
