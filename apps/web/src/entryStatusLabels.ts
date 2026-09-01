import type { EntryStatus } from "./api";

/** BH-148 dictionary-entry lifecycle, shared by the entries list and the
 * entry detail page. */
export const ENTRY_STATUS_LABELS: Record<EntryStatus, string> = {
  draft: "Чернетка",
  ready_to_review: "Очікує перевірки",
  complete: "Завершено",
};

export const ENTRY_STATUS_VARIANT: Record<
  EntryStatus,
  "warning" | "info" | "secondary"
> = {
  draft: "warning",
  ready_to_review: "info",
  complete: "secondary",
};

export const ENTRY_STATUS_ORDER: EntryStatus[] = [
  "draft",
  "ready_to_review",
  "complete",
];
