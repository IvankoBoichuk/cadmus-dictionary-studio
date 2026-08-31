import type { DictionaryStatus } from "./api";

export const DICTIONARY_STATUS_LABELS: Record<DictionaryStatus, string> = {
  draft: "Чернетка",
  configured: "Готовий до обробки",
  scanned: "Скановано",
  in_progress: "В опрацюванні",
  processed: "Опрацьовано",
  published: "Опубліковано",
};

type BadgeVariant = "warning" | "info" | "success";

export const DICTIONARY_STATUS_BADGE_VARIANT: Record<
  DictionaryStatus,
  BadgeVariant
> = {
  draft: "warning",
  configured: "info",
  scanned: "info",
  in_progress: "info",
  processed: "success",
  published: "success",
};
