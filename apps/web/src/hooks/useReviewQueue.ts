import { useCallback, useEffect, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type ReviewQueueItemResponse,
} from "../api";

export type ReviewQueueState =
  | { status: "loading" }
  | { status: "loaded"; items: ReviewQueueItemResponse[] }
  | { status: "error"; message: string };

/** Loads the cross-dictionary "awaiting review" queue for the reviewer. */
export function useReviewQueue() {
  const [state, setState] = useState<ReviewQueueState>({ status: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ status: "loading" });
    API.review.queue({ signal }).then(
      (items) => setState({ status: "loaded", items }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося завантажити чергу рецензування. Спробуйте пізніше.",
        });
      },
    );
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    // `load` resets to "loading" then fetches — same as useDictionaryEntries.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  return { state, reload: () => load() } as const;
}
