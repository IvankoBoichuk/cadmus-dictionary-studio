import { describe, expect, it } from "vitest";

import {
  normalizeIsbn,
  validateIsbn,
  validatePublicationYear,
} from "./dictionaryValidation";

describe("validatePublicationYear", () => {
  it.each([
    [1993, 2026, true],
    [1450, 2026, true],
    [2027, 2026, true],
    [1449, 2026, false],
    [2028, 2026, false],
  ])("year=%i currentYear=%i valid=%s", (year, currentYear, valid) => {
    expect(validatePublicationYear(year, currentYear) === undefined).toBe(valid);
  });
});

describe("normalizeIsbn", () => {
  it("strips hyphens and spaces and upper-cases the checksum digit", () => {
    expect(normalizeIsbn("0-306-40615-x")).toBe("030640615X");
    expect(normalizeIsbn(" 978 0306406157 ")).toBe("9780306406157");
  });
});

describe("validateIsbn", () => {
  it.each([
    ["0-306-40615-2", true],
    ["978-0-306-40615-7", true],
    ["0306406153", false],
    ["1234567890123", false],
    ["not-an-isbn", false],
  ])("isbn=%s valid=%s", (raw, valid) => {
    expect(validateIsbn(raw).error === undefined).toBe(valid);
  });
});
