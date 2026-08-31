import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Outlet, Route, Routes } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import type { DictionaryResponse } from "../api";
import { DictionaryOverviewPage } from "./DictionaryOverviewPage";

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
    status: "draft",
    title: "Словник",
    description: null,
    article_description: null,
    dictionary_type: null,
    publisher: "Наукова думка",
    publication_year: 1996,
    edition: null,
    isbn: null,
    digital_source: null,
    legal_status: null,
    license_type: null,
    permission_reference: null,
    rights_note: null,
    contributors: [],
    language_codes: ["uk"],
    created_at: "2026-08-15T12:00:00Z",
    updated_at: "2026-08-15T12:00:00Z",
    missing_required_fields: [],
    readiness_blockers: [{ code: "languages", message: "Вкажіть мову." }],
    source: null,
    ...overrides,
  };
}

function renderOverview(
  dictionary = baseDictionary(),
  onUpdated: (next: DictionaryResponse) => void = vi.fn(),
) {
  return render(
    <MemoryRouter initialEntries={["/d1"]}>
      <Routes>
        <Route
          path="/d1"
          element={<Outlet context={{ dictionary, onUpdated }} />}
        >
          <Route index element={<DictionaryOverviewPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

it("shows readiness, blockers and progress metrics", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/dictionaries/d1/pages") {
        return jsonResponse(200, { total_pages: 12 });
      }
      if (url === "/api/dictionaries/d1/scan-progress") {
        return jsonResponse(200, {
          status: "in_progress",
          total_pages: 12,
          processed_pages: 5,
          pages: [
            { page_number: 1, has_lexemes: true },
            { page_number: 2, has_lexemes: true },
            { page_number: 3, has_lexemes: false },
          ],
          total_lexemes: 40,
          completed_lexemes: 10,
          total_entries: 0,
          completed_entries: 0,
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }),
  );

  renderOverview(
    baseDictionary({
      publisher: "Наукова думка",
      publication_year: 1996,
      language_codes: ["uk", "grc"],
      legal_status: "public_domain",
      contributors: [{ name: "Борис Грінченко", role: "compiler", position: 0 }],
    }),
  );

  expect(screen.getByRole("status")).toHaveTextContent("Чернетка");
  expect(screen.getByText("Вкажіть мову.")).toBeInTheDocument();

  await waitFor(() => {
    expect(
      screen.getByText("Сторінок у діапазонах").closest("div"),
    ).toHaveTextContent("12");
    expect(screen.getByText("Лексеми").closest("div")).toHaveTextContent(
      /10\s*\/\s*40/,
    );
  });
  expect(
    screen.getByText("Опрацьовано сторінок").closest("div"),
  ).toHaveTextContent("5");
  expect(
    screen.getByText("Сторінок зі словами").closest("div"),
  ).toHaveTextContent("2");

  // North-star completion bars.
  const lexemesRow = screen.getByText("Лексеми").closest("div")!;
  expect(lexemesRow).toHaveTextContent(/25\s*%/);
  const entriesRow = screen.getByText("Статті").closest("div")!;
  expect(entriesRow).toHaveTextContent("ще немає");
  expect(
    screen.getByRole("progressbar", { name: "Лексеми: опрацьовано" }),
  ).toBeInTheDocument();

  expect(
    screen.getByRole("link", { name: "Перейти до опрацювання" }),
  ).toHaveAttribute("href", "/d1/pages");

  // "Про словник" mirrors every metadata field.
  const publisherRow = screen.getByText("Видавництво").closest("div")!;
  expect(publisherRow).toHaveTextContent("Наукова думка");
  const languagesRow = screen.getByText("Мови").closest("div")!;
  expect(languagesRow).toHaveTextContent("Українська, GRC");
  const contributorsRow = screen.getByText("Автори та укладачі").closest("div")!;
  expect(contributorsRow).toHaveTextContent("Борис Грінченко (Укладач(ка))");
  const legalRow = screen.getByText("Правовий статус").closest("div")!;
  expect(legalRow).toHaveTextContent("Суспільне надбання");
  const isbnRow = screen.getByText("ISBN").closest("div")!;
  expect(isbnRow).toHaveTextContent("—");
  expect(
    screen.getByRole("link", { name: "Редагувати" }),
  ).toHaveAttribute("href", "/d1/settings/metadata");
});

it("propagates the auto-advanced status from scan-progress", async () => {
  const onUpdated = vi.fn();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === "/api/dictionaries/d1/pages") {
        return jsonResponse(200, { total_pages: 3 });
      }
      if (url === "/api/dictionaries/d1/scan-progress") {
        return jsonResponse(200, {
          status: "processed",
          total_pages: 3,
          processed_pages: 3,
          pages: [],
          total_lexemes: 4,
          completed_lexemes: 4,
          total_entries: 4,
          completed_entries: 4,
        });
      }
      throw new Error(`Unexpected request: ${url}`);
    }),
  );

  renderOverview(baseDictionary({ status: "scanned" }), onUpdated);

  await waitFor(() =>
    expect(onUpdated).toHaveBeenCalledWith(
      expect.objectContaining({ status: "processed" }),
    ),
  );
});
