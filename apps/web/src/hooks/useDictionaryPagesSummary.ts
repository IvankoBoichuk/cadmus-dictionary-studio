import { useEffect, useState } from "react";

import { API, apiMessageFrom, isAbortError } from "../api";

export type DictionaryPagesSummaryState =
  | { status: "loading" }
  | { status: "loaded"; totalPages: number }
  | { status: "error"; message: string };

/** BH-53 AC2/AC4: loads how many pages fall within the dictionary's saved ranges. */
export function useDictionaryPagesSummary(
  dictionaryId: string,
): DictionaryPagesSummaryState {
  const [state, setState] = useState<DictionaryPagesSummaryState>({
    status: "loading",
  });

  useEffect(() => {
    const controller = new AbortController();
    API.pages.summary(dictionaryId, { signal: controller.signal }).then(
      (summary) => setState({ status: "loaded", totalPages: summary.total_pages }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося завантажити сторінки словника. Спробуйте пізніше.",
        });
      },
    );
    return () => controller.abort();
  }, [dictionaryId]);

  return state;
}
