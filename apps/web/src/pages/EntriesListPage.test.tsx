import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { EntrySummaryResponse } from "../api";
import { EntriesListPage } from "./EntriesListPage";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function entry(overrides: Partial<EntrySummaryResponse> = {}): EntrySummaryResponse {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    headword: "слово",
    status: "draft",
    field_count: 0,
    created_at: "2026-08-15T12:00:00Z",
    updated_at: "2026-08-15T12:00:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/dictionaries/${DICTIONARY_ID}/entries`]}>
      <Routes>
        <Route
          path="/dictionaries/:dictionaryId/entries"
          element={<EntriesListPage />}
        />
        <Route path="/entries/:entryId" element={<p>сторінка статті</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("EntriesListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lists entries with a link, status badge and field count", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, [
          entry({ id: "e1", headword: "абетка", status: "complete", field_count: 4 }),
          entry({ id: "e2", headword: "яблуко", status: "draft", field_count: 1 }),
        ]),
      ),
    );

    renderPage();

    const link = await screen.findByRole("link", { name: "абетка" });
    expect(link).toHaveAttribute("href", "/entries/e1");
    const row = link.closest("tr")!;
    expect(row).toHaveTextContent("Завершено");
    expect(row).toHaveTextContent("4");
    expect(screen.getByText("2 статей")).toBeInTheDocument();
  });

  it("filters by status when a chip is pressed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, [
          entry({ id: "e1", headword: "абетка", status: "complete" }),
          entry({ id: "e2", headword: "яблуко", status: "draft" }),
        ]),
      ),
    );

    renderPage();
    await screen.findByRole("link", { name: "абетка" });

    fireEvent.click(screen.getByRole("button", { name: /Завершено/ }));

    expect(screen.getByRole("link", { name: "абетка" })).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "яблуко" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("1 з 2")).toBeInTheDocument();
  });

  it("filters by a headword search query", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, [
          entry({ id: "e1", headword: "абетка" }),
          entry({ id: "e2", headword: "яблуко" }),
        ]),
      ),
    );

    renderPage();
    await screen.findByRole("link", { name: "абетка" });

    fireEvent.change(
      screen.getByPlaceholderText("Пошук за заголовним словом…"),
      { target: { value: "ябл" } },
    );

    expect(screen.getByRole("link", { name: "яблуко" })).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "абетка" }),
    ).not.toBeInTheDocument();
  });

  it("shows an empty state when the dictionary has no entries", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [])));

    renderPage();

    expect(
      await screen.findByText(/Ще немає жодної статті/),
    ).toBeInTheDocument();
  });

  it("surfaces a load error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(404, { code: "not_found", message: "Словник не знайдено." }),
      ),
    );

    renderPage();

    expect(
      await screen.findByText("Словник не знайдено."),
    ).toBeInTheDocument();
  });
});
