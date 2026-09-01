import type { EntryFieldRole } from "./api";

/** Field roles a BH-148 article-schema node can take (mirrors the backend
 * `EntryFieldRole` enum). */
export const ROLE_LABELS: Record<EntryFieldRole, string> = {
  headword: "Заголовне слово",
  part_of_speech: "Частина мови",
  meaning: "Значення",
  example: "Приклад",
  synonym: "Синонім",
  abbreviation: "Скорочення",
  geographic_label: "Географічна мітка",
  other: "Інше",
};

export const ROLE_OPTIONS: { value: EntryFieldRole; label: string }[] =
  Object.entries(ROLE_LABELS).map(([value, label]) => ({
    value: value as EntryFieldRole,
    label,
  }));

/** Structural type of a schema node, matching `ai_schema.py`'s tool schema. */
export type SchemaFieldType =
  | "string"
  | "number"
  | "boolean"
  | "date"
  | "enum"
  | "list"
  | "group";

export const TYPE_LABELS: Record<SchemaFieldType, string> = {
  string: "Текст",
  number: "Число",
  boolean: "Логічне (так/ні)",
  date: "Дата",
  enum: "Перелік",
  list: "Список",
  group: "Група",
};

export const TYPE_OPTIONS: { value: SchemaFieldType; label: string }[] =
  Object.entries(TYPE_LABELS).map(([value, label]) => ({
    value: value as SchemaFieldType,
    label,
  }));

/** Field types whose node carries an `options` list of allowed values. */
export const TYPES_WITH_OPTIONS = new Set<SchemaFieldType>(["enum"]);

/** Deepest nesting the backend accepts (top field → mid child → leaf). */
export const MAX_SCHEMA_DEPTH = 3;
