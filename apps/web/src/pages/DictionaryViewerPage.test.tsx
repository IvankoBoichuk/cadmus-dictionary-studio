import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthenticatedUser } from "../api";
import { AuthContext, type AuthContextValue } from "../authContext";
import { DictionaryViewerPage } from "./DictionaryViewerPage";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function authenticated(): AuthContextValue {
  return {
    session: { status: "authenticated", user: {} as AuthenticatedUser },
    setAuthenticated: vi.fn(),
    setAnonymous: vi.fn(),
  };
}

function renderAt(path: string) {
  return render(
    <AuthContext.Provider value={authenticated()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/dictionaries/:dictionaryId/view"
            element={<DictionaryViewerPage />}
          />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("DictionaryViewerPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("opens the page requested by the ?page= URL parameter (AC5)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { total_pages: 10 })),
    );

    renderAt("/dictionaries/dict-1/view?page=3");

    expect(await screen.findByAltText("Сторінка 3 з 10")).toBeInTheDocument();
  });

  it("defaults to page 1 when no ?page= parameter is present", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { total_pages: 10 })),
    );

    renderAt("/dictionaries/dict-1/view");

    expect(await screen.findByAltText("Сторінка 1 з 10")).toBeInTheDocument();
  });

  it("moving to the next page updates the URL so a reload keeps it (AC5)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { total_pages: 10 })),
    );

    renderAt("/dictionaries/dict-1/view?page=3");
    await screen.findByAltText("Сторінка 3 з 10");

    fireEvent.click(screen.getByRole("button", { name: "Наступна →" }));

    expect(await screen.findByAltText("Сторінка 4 з 10")).toBeInTheDocument();
  });
});
