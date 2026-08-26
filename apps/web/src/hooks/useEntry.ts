import { useCallback, useEffect, useState } from "react";

import { API, apiMessageFrom, isAbortError, type EntryResponse } from "../api";

export type EntryLoadState =
  | { status: "loading" }
  | { status: "loaded"; entry: EntryResponse }
  | { status: "error"; message: string };

/** Loads one dictionary entry, its fragments, and its structured fields (BH-148). */
export function useEntry(entryId: string) {
  const [state, setState] = useState<EntryLoadState>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    API.entries.get(entryId, { signal: controller.signal }).then(
      (entry) => setState({ status: "loaded", entry }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ?? "Не вдалося завантажити статтю. Спробуйте пізніше.",
        });
      },
    );
    return () => controller.abort();
  }, [entryId, reloadToken]);

  const setEntry = useCallback((entry: EntryResponse) => {
    setState({ status: "loaded", entry });
  }, []);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { state, setEntry, reload } as const;
}
