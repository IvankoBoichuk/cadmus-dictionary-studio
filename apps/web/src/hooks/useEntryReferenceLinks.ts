import { useCallback, useEffect, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type EntryReferenceLinkResponse,
  type ReferenceRelationType,
} from "../api";

export type EntryReferenceLinksState =
  | { status: "loading" }
  | { status: "loaded"; links: EntryReferenceLinkResponse[] }
  | { status: "error"; message: string };

/**
 * Loads the confirmed VESUM reference links for one dictionary entry and
 * offers add/remove over the list (ADR-0009). `add` rethrows so the caller
 * can surface the API's message — e.g. the 422 raised when a
 * standard-equivalent link points at a non-standard lemma.
 */
export function useEntryReferenceLinks(entryId: string) {
  const [state, setState] = useState<EntryReferenceLinksState>({
    status: "loading",
  });
  const [removingId, setRemovingId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    API.entries.listReferenceLinks(entryId, { signal: controller.signal }).then(
      (links) => setState({ status: "loaded", links }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося завантажити прив'язки до довідкового словника.",
        });
      },
    );
    return () => controller.abort();
  }, [entryId]);

  const add = useCallback(
    async (
      referenceLemmaId: string,
      relationType: ReferenceRelationType,
    ): Promise<EntryReferenceLinkResponse> => {
      const created = await API.entries.createReferenceLink(entryId, {
        reference_lemma_id: referenceLemmaId,
        relation_type: relationType,
      });
      setState((current) =>
        current.status === "loaded"
          ? {
              status: "loaded",
              links: current.links.some((link) => link.id === created.id)
                ? current.links.map((link) =>
                    link.id === created.id ? created : link,
                  )
                : [...current.links, created],
            }
          : current,
      );
      return created;
    },
    [entryId],
  );

  const remove = useCallback(
    async (linkId: string): Promise<void> => {
      setRemovingId(linkId);
      try {
        await API.entries.deleteReferenceLink(entryId, linkId);
        setState((current) =>
          current.status === "loaded"
            ? {
                status: "loaded",
                links: current.links.filter((link) => link.id !== linkId),
              }
            : current,
        );
      } finally {
        setRemovingId(null);
      }
    },
    [entryId],
  );

  return { state, add, remove, removingId } as const;
}
