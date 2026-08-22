import { useCallback, useEffect, useRef, useState } from "react";

import { API, apiMessageFrom, type LexemeSuggestion } from "../api";

const POLL_INTERVAL_MS = 1500;

export type OcrSuggestionsState =
  | { status: "idle" }
  | { status: "starting" }
  | { status: "queued" | "running"; taskId: string }
  | { status: "succeeded"; taskId: string; suggestions: LexemeSuggestion[] }
  | { status: "failed"; message: string };

/** Suggests lexeme boundaries from ALTO/Tesseract, enqueued on the worker and polled here. */
export function useOcrSuggestions(dictionaryId: string, pageNumber: number) {
  const [state, setState] = useState<OcrSuggestionsState>({ status: "idle" });
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
      API.ocrSuggestions.getTask(dictionaryId, pageNumber, taskId).then(
        (task) => {
          if (task.status === "succeeded") {
            stopPolling();
            setState({ status: "succeeded", taskId, suggestions: task.suggestions ?? [] });
          } else if (task.status === "failed") {
            stopPolling();
            setState({
              status: "failed",
              message: task.error ?? "Не вдалося розпізнати текст на сторінці.",
            });
          } else {
            setState({ status: task.status, taskId });
          }
        },
        (error: unknown) => {
          stopPolling();
          setState({
            status: "failed",
            message:
              apiMessageFrom(error) ?? "Не вдалося перевірити статус розпізнавання.",
          });
        },
      );
    },
    [dictionaryId, pageNumber, stopPolling],
  );

  const trigger = useCallback(async () => {
    stopPolling();
    setState({ status: "starting" });
    try {
      const response = await API.ocrSuggestions.enqueue(dictionaryId, pageNumber);
      setState({ status: "queued", taskId: response.task_id });
      pollingRef.current = setInterval(() => poll(response.task_id), POLL_INTERVAL_MS);
    } catch (error) {
      setState({
        status: "failed",
        message: apiMessageFrom(error) ?? "Не вдалося запустити розпізнавання.",
      });
    }
  }, [dictionaryId, pageNumber, poll, stopPolling]);

  const dismissSuggestion = useCallback((suggestion: LexemeSuggestion) => {
    setState((current) =>
      current.status === "succeeded"
        ? {
            ...current,
            suggestions: current.suggestions.filter((candidate) => candidate !== suggestion),
          }
        : current,
    );
  }, []);

  const reset = useCallback(() => {
    stopPolling();
    setState({ status: "idle" });
  }, [stopPolling]);

  return { state, trigger, dismissSuggestion, reset };
}
