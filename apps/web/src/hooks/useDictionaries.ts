import { useCallback, useEffect, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type DictionaryListResponse,
} from "../api";

export type DictionariesLoadState =
  | { status: "loading" }
  | { status: "loaded"; dictionaries: DictionaryListResponse }
  | { status: "error"; message: string };

export type DeleteState = { pending: boolean; error: string | undefined };

/** Loads the caller's dictionaries and offers a delete action over the list. */
export function useDictionaries(): {
  state: DictionariesLoadState;
  deleteState: Record<string, DeleteState | undefined>;
  remove: (dictionaryId: string) => Promise<void>;
} {
  const [state, setState] = useState<DictionariesLoadState>({ status: "loading" });
  const [deleteState, setDeleteState] = useState<
    Record<string, DeleteState | undefined>
  >({});

  useEffect(() => {
    const controller = new AbortController();
    API.dictionaries.list({ signal: controller.signal }).then(
      (dictionaries) => setState({ status: "loaded", dictionaries }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося завантажити словники. Спробуйте пізніше.",
        });
      },
    );
    return () => controller.abort();
  }, []);

  const remove = useCallback(async (dictionaryId: string) => {
    setDeleteState((current) => ({
      ...current,
      [dictionaryId]: { pending: true, error: undefined },
    }));
    try {
      await API.dictionaries.delete(dictionaryId);
      setState((current) =>
        current.status === "loaded"
          ? {
              status: "loaded",
              dictionaries: current.dictionaries.filter(
                (dictionary) => dictionary.id !== dictionaryId,
              ),
            }
          : current,
      );
      setDeleteState((current) => {
        const rest = { ...current };
        delete rest[dictionaryId];
        return rest;
      });
    } catch (error) {
      setDeleteState((current) => ({
        ...current,
        [dictionaryId]: {
          pending: false,
          error:
            apiMessageFrom(error) ?? "Не вдалося видалити словник. Спробуйте пізніше.",
        },
      }));
    }
  }, []);

  return { state, deleteState, remove };
}
