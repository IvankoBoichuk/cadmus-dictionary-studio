import { useEffect, useState } from "react";

import { API, apiMessageFrom, isAbortError, type DictionaryResponse } from "../api";

export type DictionaryLoadState =
  | { status: "loading" }
  | { status: "loaded"; dictionary: DictionaryResponse }
  | { status: "error"; message: string };

/** Loads an existing dictionary draft for editing, without touching its PDF. */
export function useDictionary(dictionaryId: string): DictionaryLoadState {
  const [state, setState] = useState<DictionaryLoadState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    API.dictionaries.get(dictionaryId, { signal: controller.signal }).then(
      (dictionary) => setState({ status: "loaded", dictionary }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося завантажити словник. Спробуйте пізніше.",
        });
      },
    );
    return () => controller.abort();
  }, [dictionaryId]);

  return state;
}
