/**
 * Curated ISO 639-1 language options for the dictionary metadata form.
 *
 * The backend accepts the complete ISO 639-1 code set (see
 * `cadmus.sources.domain.ISO_639_1_CODES`); this list is a practical,
 * reviewable subset for the picker UI rather than all ~180 codes. Expanding
 * it (or adding search) is a documented follow-up, not a backend limitation.
 */
export const LANGUAGE_OPTIONS: readonly { code: string; name: string }[] = [
  { code: "uk", name: "Українська" },
  { code: "en", name: "English" },
  { code: "de", name: "Deutsch" },
  { code: "fr", name: "Français" },
  { code: "pl", name: "Polski" },
  { code: "ru", name: "Русский" },
  { code: "cs", name: "Čeština" },
  { code: "sk", name: "Slovenčina" },
  { code: "be", name: "Беларуская" },
  { code: "bg", name: "Български" },
  { code: "sr", name: "Српски" },
  { code: "hr", name: "Hrvatski" },
  { code: "ro", name: "Română" },
  { code: "hu", name: "Magyar" },
  { code: "it", name: "Italiano" },
  { code: "es", name: "Español" },
  { code: "pt", name: "Português" },
  { code: "nl", name: "Nederlands" },
  { code: "sv", name: "Svenska" },
  { code: "el", name: "Ελληνικά" },
  { code: "tr", name: "Türkçe" },
  { code: "la", name: "Latina" },
  { code: "he", name: "עברית" },
  { code: "ar", name: "العربية" },
  { code: "zh", name: "中文" },
  { code: "ja", name: "日本語" },
];

const LANGUAGE_NAME_BY_CODE = new Map(
  LANGUAGE_OPTIONS.map((option) => [option.code, option.name]),
);

/** `["uk", "grc"]` -> `"Українська, GRC"`. Unknown codes fall back to the
 * upper-cased code (the backend accepts the full ISO 639-1 set). */
export function formatLanguages(codes: readonly string[]): string {
  return codes
    .map((code) => LANGUAGE_NAME_BY_CODE.get(code) ?? code.toUpperCase())
    .join(", ");
}
