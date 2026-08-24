import { useCallback, useEffect, useRef, useState } from "react";

import { API, apiMessageFrom } from "../api";

const POLL_INTERVAL_MS = 1500;

export type DictionaryScanState =
  | { status: "idle" }
  | { status: "starting" }
  | {
      status: "queued" | "running";
      taskId: string;
      processedPages: number;
      totalPages: number;
      createdLexemes: number;
    }
  | {
      status: "succeeded";
      taskId: string;
      processedPages: number;
      totalPages: number;
      createdLexemes: number;
    }
  | { status: "failed"; message: string };

/**
 * Queues OCR across every unscanned page of a dictionary, persisting each
 * surviving suggestion directly as a draft lexeme, and polls task progress.
 */
export function useDictionaryScan(dictionaryId: string) {
  const [state, setState] = useState<DictionaryScanState>({ status: "idle" });
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
      API.ocrScan.getTask(dictionaryId, taskId).then(
        (task) => {
          if (task.status === "succeeded") {
            stopPolling();
            setState({
              status: "succeeded",
              taskId,
              processedPages: task.processed_pages,
              totalPages: task.total_pages,
              createdLexemes: task.created_lexemes,
            });
          } else if (task.status === "failed") {
            stopPolling();
            setState({
              status: "failed",
              message: task.error ?? "Не вдалося опрацювати чергу розпізнавання.",
            });
          } else {
            setState({
              status: task.status,
              taskId,
              processedPages: task.processed_pages,
              totalPages: task.total_pages,
              createdLexemes: task.created_lexemes,
            });
          }
        },
        (error: unknown) => {
          stopPolling();
          setState({
            status: "failed",
            message: apiMessageFrom(error) ?? "Не вдалося перевірити статус черги.",
          });
        },
      );
    },
    [dictionaryId, stopPolling],
  );

  const trigger = useCallback(async () => {
    stopPolling();
    setState({ status: "starting" });
    try {
      const response = await API.ocrScan.enqueue(dictionaryId);
      setState({
        status: "queued",
        taskId: response.task_id,
        processedPages: 0,
        totalPages: 0,
        createdLexemes: 0,
      });
      pollingRef.current = setInterval(() => poll(response.task_id), POLL_INTERVAL_MS);
    } catch (error) {
      setState({
        status: "failed",
        message: apiMessageFrom(error) ?? "Не вдалося запустити чергу розпізнавання.",
      });
    }
  }, [dictionaryId, poll, stopPolling]);

  const reset = useCallback(() => {
    stopPolling();
    setState({ status: "idle" });
  }, [stopPolling]);

  return { state, trigger, reset };
}
