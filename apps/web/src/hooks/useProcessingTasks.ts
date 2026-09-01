import { useCallback, useEffect, useRef, useState } from "react";

import {
  API,
  apiMessageFrom,
  isAbortError,
  type ProcessingTaskResponse,
} from "../api";
import { PROCESSING_TASK_ACTIVE_STATUSES } from "../processingTaskLabels";

const POLL_INTERVAL_MS = 4000;

export type ProcessingTasksState =
  | { status: "loading" }
  | { status: "loaded"; tasks: ProcessingTaskResponse[] }
  | { status: "error"; message: string };

function hasActive(tasks: ProcessingTaskResponse[]): boolean {
  return tasks.some((task) =>
    PROCESSING_TASK_ACTIVE_STATUSES.includes(task.status),
  );
}

/**
 * Loads a dictionary's recorded async jobs and keeps the list fresh:
 * while any task is queued or running it re-fetches every few seconds,
 * then stops until something changes. `retry` rethrows so the caller can
 * surface the API's 409 message.
 */
export function useProcessingTasks(dictionaryId: string) {
  const [state, setState] = useState<ProcessingTasksState>({ status: "loading" });
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const disposedRef = useRef(false);
  // Indirection so `refresh` can re-arm the poll loop without referencing
  // itself (which the react-hooks lint rules disallow).
  const refreshRef = useRef<() => void>(() => {});

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const refresh = useCallback(async () => {
    let tasks: ProcessingTaskResponse[];
    try {
      tasks = await API.tasks.listForDictionary(dictionaryId, { limit: 100 });
    } catch (error) {
      if (isAbortError(error) || disposedRef.current) return;
      setState({
        status: "error",
        message:
          apiMessageFrom(error) ??
          "Не вдалося завантажити список задач. Спробуйте пізніше.",
      });
      return;
    }
    if (disposedRef.current) return;
    setState({ status: "loaded", tasks });
    clearTimer();
    if (hasActive(tasks)) {
      timerRef.current = window.setTimeout(
        () => refreshRef.current(),
        POLL_INTERVAL_MS,
      );
    }
  }, [dictionaryId, clearTimer]);

  useEffect(() => {
    refreshRef.current = () => void refresh();
  }, [refresh]);

  useEffect(() => {
    disposedRef.current = false;
    void refresh();
    return () => {
      disposedRef.current = true;
      clearTimer();
    };
  }, [refresh, clearTimer]);

  const retry = useCallback(
    async (taskId: string): Promise<ProcessingTaskResponse> => {
      setRetryingId(taskId);
      try {
        const created = await API.tasks.retry(dictionaryId, taskId);
        setState((current) =>
          current.status === "loaded"
            ? { status: "loaded", tasks: [created, ...current.tasks] }
            : current,
        );
        void refresh();
        return created;
      } finally {
        setRetryingId(null);
      }
    },
    [dictionaryId, refresh],
  );

  return {
    state,
    retry,
    retryingId,
    refresh: () => void refresh(),
  } as const;
}
