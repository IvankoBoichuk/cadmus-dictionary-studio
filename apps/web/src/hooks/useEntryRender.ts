import { useCallback, useEffect, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type EntryRenderResponse,
} from "../api";

export type EntryRenderState =
  | { status: "loading" }
  | {
      status: "loaded";
      markdown: string | null;
      reason: EntryRenderResponse["reason"];
      error: EntryRenderResponse["error"];
    }
  | { status: "error"; message: string };

/**
 * Loads the Markdown rendering of an entry via its schema's presentation
 * formula (BH-148). `reload()` re-fetches after the entry's fields change.
 */
export function useEntryRender(entryId: string) {
  const [state, setState] = useState<EntryRenderState>({ status: "loading" });
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    API.entries.render(entryId, { signal: controller.signal }).then(
      (response) =>
        setState({
          status: "loaded",
          markdown: response.markdown,
          reason: response.reason,
          error: response.error,
        }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося побудувати перегляд статті. Спробуйте пізніше.",
        });
      },
    );
    return () => controller.abort();
  }, [entryId, reloadToken]);

  const reload = useCallback(() => setReloadToken((token) => token + 1), []);

  return { state, reload } as const;
}
