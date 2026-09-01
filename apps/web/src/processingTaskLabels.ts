import type { ProcessingTaskKind, ProcessingTaskStatus } from "./api";

export const PROCESSING_TASK_KIND_LABELS: Record<ProcessingTaskKind, string> = {
  dictionary_scan: "OCR-скан словника",
  entry_extraction: "Розбір структури статті",
  article_schema_generation: "Генерація схеми статті",
  ocr_suggestions: "OCR-підказки сторінки",
};

export const PROCESSING_TASK_STATUS_LABELS: Record<
  ProcessingTaskStatus,
  string
> = {
  queued: "У черзі",
  running: "Виконується",
  succeeded: "Успішно",
  failed: "Помилка",
};

export const PROCESSING_TASK_STATUS_VARIANT: Record<
  ProcessingTaskStatus,
  "info" | "warning" | "secondary" | "danger"
> = {
  queued: "info",
  running: "warning",
  succeeded: "secondary",
  failed: "danger",
};

export const PROCESSING_TASK_ACTIVE_STATUSES: ProcessingTaskStatus[] = [
  "queued",
  "running",
];

/** `"1 хв 12 с"` from two ISO timestamps; `null` when either is missing. */
export function formatTaskDuration(
  startedAt: string | null,
  finishedAt: string | null,
): string | null {
  if (!startedAt || !finishedAt) return null;
  const ms = new Date(finishedAt).getTime() - new Date(startedAt).getTime();
  if (!Number.isFinite(ms) || ms < 0) return null;
  const totalSeconds = Math.round(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes > 0 ? `${minutes} хв ${seconds} с` : `${seconds} с`;
}
