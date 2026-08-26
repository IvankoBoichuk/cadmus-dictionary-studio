import { useCallback, useEffect, useRef, useState } from "react";

import { API, apiMessageFrom } from "../api";

const POLL_INTERVAL_MS = 1500;

export type ArticleSchemaGenerationState =
  | { status: "idle" }
  | { status: "starting" }
  | { status: "queued" | "running"; taskId: string }
  | { status: "succeeded"; taskId: string; schemaId: string }
  | { status: "failed"; message: string };

/** Enqueues AI article-schema generation from a dictionary's article_description and polls it. */
export function useArticleSchemaGeneration(dictionaryId: string) {
  const [state, setState] = useState<ArticleSchemaGenerationState>({ status: "idle" });
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
      API.articleSchemas.getGenerationTask(dictionaryId, taskId).then(
        (task) => {
          if (task.status === "succeeded") {
            stopPolling();
            setState({ status: "succeeded", taskId, schemaId: task.schema_id ?? "" });
          } else if (task.status === "failed") {
            stopPolling();
            setState({
              status: "failed",
              message: task.error ?? "Не вдалося згенерувати схему статті.",
            });
          } else {
            setState({ status: task.status, taskId });
          }
        },
        (error: unknown) => {
          stopPolling();
          setState({
            status: "failed",
            message: apiMessageFrom(error) ?? "Не вдалося перевірити статус генерації.",
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
      const response = await API.articleSchemas.generate(dictionaryId);
      setState({ status: "queued", taskId: response.task_id });
      pollingRef.current = setInterval(() => poll(response.task_id), POLL_INTERVAL_MS);
    } catch (error) {
      setState({
        status: "failed",
        message: apiMessageFrom(error) ?? "Не вдалося запустити генерацію схеми.",
      });
    }
  }, [dictionaryId, poll, stopPolling]);

  const reset = useCallback(() => {
    stopPolling();
    setState({ status: "idle" });
  }, [stopPolling]);

  return { state, trigger, reset };
}
