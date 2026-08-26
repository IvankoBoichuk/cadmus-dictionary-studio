import type { LexemeStatus } from "./api";

export const LEXEME_STATUS_LABELS: Record<LexemeStatus, string> = {
  draft: "Чернетка",
  ready_to_process: "Готова до розбиття",
  ready_to_review: "Потребує перевірки",
  complete: "Завершено",
};
