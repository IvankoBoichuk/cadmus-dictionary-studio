import { useCallback, useEffect, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type EntrySummaryResponse,
} from "../api";

export type DictionaryEntriesState =
  | { status: "loading" }
  | { status: "loaded"; entries: EntrySummaryResponse[] }
  | { status: "error"; message: string };

/** Loads a dictionary's structured entries for the list page (BH-148). */
export function useDictionaryEntries(dictionaryId: string) {
  const [state, setState] = useState<DictionaryEntriesState>({
    status: "loading",
  });

  const load = useCallback(
    (signal?: AbortSignal) => {
      setState({ status: "loading" });
      API.entries.listForDictionary(dictionaryId, { signal }).then(
        (entries) => setState({ status: "loaded", entries }),
        (error: unknown) => {
          if (isAbortError(error)) return;
          setState({
            status: "error",
            message:
              apiMessageFrom(error) ??
              "Не вдалося завантажити статті словника. Спробуйте пізніше.",
          });
        },
      );
    },
    [dictionaryId],
  );

  useEffect(() => {
    const controller = new AbortController();
    // `load` resets to "loading" then fetches — same as useAbbreviations.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  return { state, reload: () => load() } as const;
}
