import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useOutletContext } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import type { DictionaryResponse } from "../api";
import { DictionaryLayout } from "./DictionaryLayout";

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function baseDictionary(
  overrides: Partial<DictionaryResponse> = {},
): DictionaryResponse {
  return {
    id: "d1",
    status: "configured",
    title: "Словник Грінченка",
    description: null,
    article_description: null,
    dictionary_type: null,
    publisher: null,
    publication_year: null,
    edition: null,
    isbn: null,
    digital_source: null,
    legal_status: null,
    license_type: null,
    permission_reference: null,
    rights_note: null,
    contributors: [],
    language_codes: [],
    created_at: "2026-08-15T12:00:00Z",
    updated_at: "2026-08-15T12:00:00Z",
    missing_required_fields: [],
    readiness_blockers: [],
    source: null,
    ...overrides,
  };
}

function Probe() {
  const ctx = useOutletContext<{ dictionary: DictionaryResponse }>();
  return <p>probe:{ctx.dictionary.title}</p>;
}

function renderLayout() {
  return render(
    <MemoryRouter initialEntries={["/dictionaries/d1"]}>
      <Routes>
        <Route path="/dictionaries/:dictionaryId" element={<DictionaryLayout />}>
          <Route index element={<Probe />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

it("renders the header, primary tabs and passes the dictionary to child routes", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/dictionaries/d1") {
        return jsonResponse(200, baseDictionary());
      }
      throw new Error(`Unexpected request: ${String(input)}`);
    }),
  );

  renderLayout();

  expect(
    await screen.findByRole("heading", { level: 1, name: "Словник Грінченка" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Готовий до обробки")).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Сторінки та слова" }),
  ).toHaveAttribute("href", "/dictionaries/d1/pages");
  expect(screen.getByRole("link", { name: "Налаштування" })).toHaveAttribute(
    "href",
    "/dictionaries/d1/settings",
  );
  expect(screen.getByText("probe:Словник Грінченка")).toBeInTheDocument();
});

it("shows an alert when the dictionary fails to load", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(jsonResponse(500, { message: "boom" })),
  );

  renderLayout();

  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(screen.queryByText(/^probe:/)).not.toBeInTheDocument();
});
