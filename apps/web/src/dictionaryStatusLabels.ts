import type { DictionaryStatus } from "./api";

export const DICTIONARY_STATUS_LABELS: Record<DictionaryStatus, string> = {
  draft: "Чернетка",
  configured: "Готовий до обробки",
  scanned: "Скановано",
};

export const DICTIONARY_STATUS_BADGE_VARIANT: Record<
  DictionaryStatus,
  "warning" | "success"
> = {
  draft: "warning",
  configured: "success",
  scanned: "success",
};
