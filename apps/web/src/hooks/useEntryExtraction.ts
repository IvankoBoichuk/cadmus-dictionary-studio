import { useCallback, useEffect, useRef, useState } from "react";

import { API, apiMessageFrom } from "../api";

const POLL_INTERVAL_MS = 1500;

export type EntryExtractionState =
  | { status: "idle" }
  | { status: "starting" }
  | { status: "queued" | "running"; taskId: string }
  | { status: "succeeded"; taskId: string; createdFields: number }
  | { status: "failed"; message: string };

/** Enqueues AI field extraction for one entry against its dictionary's active schema, and polls it. */
export function useEntryExtraction(entryId: string) {
  const [state, setState] = useState<EntryExtractionState>({ status: "idle" });
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const poll = useCallback(
    (taskId: string) => {
      API.entries.getExtractionTask(entryId, taskId).then(
        (task) => {
          if (task.status === "succeeded") {
            stopPolling();
            setState({ status: "succeeded", taskId, createdFields: task.created_fields });
          } else if (task.status === "failed") {
            stopPolling();
            setState({
              status: "failed",
              message: task.error ?? "Не вдалося розпізнати структуру статті.",
            });
          } else {
            setState({ status: task.status, taskId });
          }
        },
        (error: unknown) => {
          stopPolling();
          setState({
            status: "failed",
            message: apiMessageFrom(error) ?? "Не вдалося перевірити статус розпізнавання.",
          });
        },
      );
    },
    [entryId, stopPolling],
  );

  const trigger = useCallback(async () => {
    stopPolling();
    setState({ status: "starting" });
    try {
      const response = await API.entries.extract(entryId);
      setState({ status: "queued", taskId: response.task_id });
      pollingRef.current = setInterval(() => poll(response.task_id), POLL_INTERVAL_MS);
    } catch (error) {
      setState({
        status: "failed",
        message: apiMessageFrom(error) ?? "Не вдалося запустити розпізнавання структури.",
      });
    }
  }, [entryId, poll, stopPolling]);

  const reset = useCallback(() => {
    stopPolling();
    setState({ status: "idle" });
  }, [stopPolling]);

  return { state, trigger, reset };
}
