/**
 * Client-side mirrors of the backend's year/ISBN rules
 * (`cadmus.sources.domain`). These are a usability layer only — the server
 * remains authoritative and re-validates every value it receives.
 */

export const MIN_PUBLICATION_YEAR = 1450;

export function validatePublicationYear(
  year: number,
  currentYear: number = new Date().getFullYear(),
): string | undefined {
  if (!Number.isInteger(year) || year < MIN_PUBLICATION_YEAR || year > currentYear + 1) {
    return `Рік видання має бути в межах від ${MIN_PUBLICATION_YEAR} до ${currentYear + 1}.`;
  }
  return undefined;
}

export function normalizeIsbn(raw: string): string {
  return raw.replace(/[\s-]/g, "").toUpperCase();
}

function isbn10ChecksumValid(value: string): boolean {
  if (!/^\d{9}[\dX]$/.test(value)) return false;
  let total = 0;
  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    const digit = char === "X" ? 10 : Number(char);
    total += (10 - index) * digit;
  }
  return total % 11 === 0;
}

function isbn13ChecksumValid(value: string): boolean {
  if (!/^\d{13}$/.test(value)) return false;
  let total = 0;
  for (let index = 0; index < value.length; index += 1) {
    total += Number(value[index]) * (index % 2 === 0 ? 1 : 3);
  }
  return total % 10 === 0;
}

export function validateIsbn(raw: string): { normalized: string; error?: string } {
  const normalized = normalizeIsbn(raw);
  if (normalized.length === 10) {
    return isbn10ChecksumValid(normalized)
      ? { normalized }
      : { normalized, error: "Некоректна контрольна сума ISBN-10." };
  }
  if (normalized.length === 13) {
    return isbn13ChecksumValid(normalized)
      ? { normalized }
      : { normalized, error: "Некоректна контрольна сума ISBN-13." };
  }
  return { normalized, error: "ISBN має містити 10 чи 13 символів." };
}
