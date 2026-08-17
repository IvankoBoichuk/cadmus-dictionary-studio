import { useCallback, useEffect, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type SettlementMappingResponse,
} from "../api";

export type SettlementsLoadState =
  | { status: "loading" }
  | { status: "loaded"; mappings: SettlementMappingResponse[] }
  | { status: "error"; message: string };

export type DeleteState = { pending: boolean; error: string | undefined };

/** Loads a dictionary's settlement mappings and offers CRUD actions over the list. */
export function useSettlements(dictionaryId: string) {
  const [state, setState] = useState<SettlementsLoadState>({ status: "loading" });
  const [deleteState, setDeleteState] = useState<
    Record<string, DeleteState | undefined>
  >({});

  const load = useCallback(
    (signal?: AbortSignal) => {
      setState({ status: "loading" });
      API.settlements.list(dictionaryId, { signal }).then(
        (mappings) => setState({ status: "loaded", mappings }),
        (error: unknown) => {
          if (isAbortError(error)) return;
          setState({
            status: "error",
            message:
              apiMessageFrom(error) ??
              "Не вдалося завантажити географічні мітки. Спробуйте пізніше.",
          });
        },
      );
    },
    [dictionaryId],
  );

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const upsert = useCallback((item: SettlementMappingResponse) => {
    setState((current) =>
      current.status === "loaded"
        ? {
            status: "loaded",
            mappings: current.mappings.some((m) => m.id === item.id)
              ? current.mappings.map((m) => (m.id === item.id ? item : m))
              : [...current.mappings, item],
          }
        : current,
    );
  }, []);

  const mergeImported = useCallback((items: SettlementMappingResponse[]) => {
    if (items.length === 0) return;
    setState((current) =>
      current.status === "loaded"
        ? { status: "loaded", mappings: [...current.mappings, ...items] }
        : current,
    );
  }, []);

  const remove = useCallback(
    async (mappingId: string) => {
      setDeleteState((current) => ({
        ...current,
        [mappingId]: { pending: true, error: undefined },
      }));
      try {
        await API.settlements.delete(dictionaryId, mappingId);
        setState((current) =>
          current.status === "loaded"
            ? {
                status: "loaded",
                mappings: current.mappings.filter((m) => m.id !== mappingId),
              }
            : current,
        );
        setDeleteState((current) => {
          const rest = { ...current };
          delete rest[mappingId];
          return rest;
        });
      } catch (error) {
        setDeleteState((current) => ({
          ...current,
          [mappingId]: {
            pending: false,
            error:
              apiMessageFrom(error) ??
              "Не вдалося видалити географічну мітку. Спробуйте пізніше.",
          },
        }));
      }
    },
    [dictionaryId],
  );

  const confirm = useCallback(
    async (mappingId: string) => {
      const confirmed = await API.settlements.confirm(dictionaryId, mappingId);
      upsert(confirmed);
      return confirmed;
    },
    [dictionaryId, upsert],
  );

  const unconfirm = useCallback(
    async (mappingId: string) => {
      const reverted = await API.settlements.unconfirm(dictionaryId, mappingId);
      upsert(reverted);
      return reverted;
    },
    [dictionaryId, upsert],
  );

  return {
    state,
    deleteState,
    remove,
    upsert,
    mergeImported,
    confirm,
    unconfirm,
    reload: () => load(),
  } as const;
}
