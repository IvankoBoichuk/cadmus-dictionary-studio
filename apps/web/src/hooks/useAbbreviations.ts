import { useCallback, useEffect, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type AbbreviationResponse,
} from "../api";

export type AbbreviationsLoadState =
  | { status: "loading" }
  | { status: "loaded"; abbreviations: AbbreviationResponse[] }
  | { status: "error"; message: string };

export type DeleteState = { pending: boolean; error: string | undefined };

/** Loads a dictionary's abbreviations and offers CRUD actions over the list. */
export function useAbbreviations(dictionaryId: string) {
  const [state, setState] = useState<AbbreviationsLoadState>({ status: "loading" });
  const [deleteState, setDeleteState] = useState<
    Record<string, DeleteState | undefined>
  >({});

  const load = useCallback(
    (signal?: AbortSignal) => {
      setState({ status: "loading" });
      API.abbreviations.list(dictionaryId, { signal }).then(
        (abbreviations) => setState({ status: "loaded", abbreviations }),
        (error: unknown) => {
          if (isAbortError(error)) return;
          setState({
            status: "error",
            message:
              apiMessageFrom(error) ??
              "Не вдалося завантажити скорочення. Спробуйте пізніше.",
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

  const upsert = useCallback((item: AbbreviationResponse) => {
    setState((current) =>
      current.status === "loaded"
        ? {
            status: "loaded",
            abbreviations: current.abbreviations.some((a) => a.id === item.id)
              ? current.abbreviations.map((a) => (a.id === item.id ? item : a))
              : [...current.abbreviations, item],
          }
        : current,
    );
  }, []);

  const mergeImported = useCallback((items: AbbreviationResponse[]) => {
    if (items.length === 0) return;
    setState((current) =>
      current.status === "loaded"
        ? { status: "loaded", abbreviations: [...current.abbreviations, ...items] }
        : current,
    );
  }, []);

  const remove = useCallback(
    async (abbreviationId: string) => {
      setDeleteState((current) => ({
        ...current,
        [abbreviationId]: { pending: true, error: undefined },
      }));
      try {
        await API.abbreviations.delete(dictionaryId, abbreviationId);
        setState((current) =>
          current.status === "loaded"
            ? {
                status: "loaded",
                abbreviations: current.abbreviations.filter(
                  (a) => a.id !== abbreviationId,
                ),
              }
            : current,
        );
        setDeleteState((current) => {
          const rest = { ...current };
          delete rest[abbreviationId];
          return rest;
        });
      } catch (error) {
        setDeleteState((current) => ({
          ...current,
          [abbreviationId]: {
            pending: false,
            error:
              apiMessageFrom(error) ??
              "Не вдалося видалити скорочення. Спробуйте пізніше.",
          },
        }));
      }
    },
    [dictionaryId],
  );

  return {
    state,
    deleteState,
    remove,
    upsert,
    mergeImported,
    reload: () => load(),
  } as const;
}
