/** Locale-aware number formatting. The UI is Ukrainian, so counts, percentages
 * and the like go through `Intl` rather than raw string interpolation. */

const UK_LOCALE = "uk";

const integerFormat = new Intl.NumberFormat(UK_LOCALE, {
  maximumFractionDigits: 0,
});

const percentFormat = new Intl.NumberFormat(UK_LOCALE, {
  style: "percent",
  maximumFractionDigits: 0,
});

const dateFormat = new Intl.DateTimeFormat(UK_LOCALE, {
  day: "numeric",
  month: "long",
  year: "numeric",
});

const dateTimeFormat = new Intl.DateTimeFormat(UK_LOCALE, {
  day: "numeric",
  month: "long",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

/** `1234` -> `"1 234"`. */
export function formatNumber(value: number): string {
  return integerFormat.format(value);
}

/** `0.83` -> `"83 %"`. Pass a 0..1 ratio, not an already-multiplied percentage. */
export function formatPercent(ratio: number): string {
  return percentFormat.format(ratio);
}

/** ISO 8601 timestamp -> `"16 серпня 2026 р."`. Invalid input is returned as-is. */
export function formatDate(iso: string): string {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? iso : dateFormat.format(parsed);
}

/** ISO 8601 timestamp -> `"16 серпня 2026 р., 14:05"`. Invalid input is returned as-is. */
export function formatDateTime(iso: string): string {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? iso : dateTimeFormat.format(parsed);
}
