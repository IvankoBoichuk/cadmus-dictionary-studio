import { useEffect, useState } from "react";

import { API, apiMessageFrom, isAbortError, type ScanProgressResponse } from "../api";

export type ScanProgressState =
  | { status: "loading" }
  | { status: "loaded"; progress: ScanProgressResponse }
  | { status: "error"; message: string };

/**
 * BH-57: loads a dictionary's scan progress.
 *
 * ``refreshToken`` lets the caller force a refetch (e.g. after the current
 * page's lexeme count changes) without the hook needing to know why.
 */
export function useScanProgress(
  dictionaryId: string,
  refreshToken: number,
): ScanProgressState {
  const [state, setState] = useState<ScanProgressState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    API.scanProgress.get(dictionaryId, { signal: controller.signal }).then(
      (progress) => setState({ status: "loaded", progress }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ?? "Не вдалося завантажити прогрес сканування.",
        });
      },
    );
    return () => controller.abort();
  }, [dictionaryId, refreshToken]);

  return state;
}
