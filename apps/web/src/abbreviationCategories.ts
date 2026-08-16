import type { AbbreviationCategory } from "./api";

export const CATEGORY_OPTIONS: { value: AbbreviationCategory; label: string }[] = [
  { value: "part_of_speech", label: "Частина мови" },
  { value: "grammar", label: "Граматика" },
  { value: "usage", label: "Вживання" },
  { value: "geography", label: "Географія" },
  { value: "source", label: "Джерело" },
  { value: "other", label: "Інше" },
];

export const CATEGORY_LABELS: Record<AbbreviationCategory, string> =
  Object.fromEntries(
    CATEGORY_OPTIONS.map((option) => [option.value, option.label]),
  ) as Record<AbbreviationCategory, string>;
