import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthenticatedUser, ReferenceLexiconResponse } from "../api";
import { AuthContext, type AuthContextValue } from "../authContext";
import { ReferenceLexiconPage } from "./ReferenceLexiconPage";

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

function lexicon(
  overrides: Partial<ReferenceLexiconResponse> = {},
): ReferenceLexiconResponse {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    code: "vesum",
    name: "Великий електронний словник української мови",
    language_code: "uk",
    version: "6.5.0",
    source_url: "https://github.com/brown-uk/dict_uk",
    license_id: "CC-BY-NC-SA-4.0",
    source_commit: "abc1234",
    checksum: "sha256:deadbeef",
    imported_at: "2026-08-31T09:00:00Z",
    ...overrides,
  };
}

function renderAt(path: string) {
  return render(
    <AuthContext.Provider value={authenticated()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/reference-lexicons/:code"
            element={<ReferenceLexiconPage />}
          />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("ReferenceLexiconPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the imported lexicon's metadata and a lemma search box", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, lexicon())),
    );

    renderAt("/reference-lexicons/vesum");

    expect(
      await screen.findByRole("heading", {
        name: "Великий електронний словник української мови",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("6.5.0")).toBeInTheDocument();
    expect(screen.getByText("CC-BY-NC-SA-4.0")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Пошук леми або словоформи"),
    ).toBeInTheDocument();
  });

  it("explains when the lexicon has not been imported", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(404, { code: "not_found", message: "не імпортовано" }),
        ),
    );

    renderAt("/reference-lexicons/vesum");

    expect(
      await screen.findByText(/ще не імпортовано/),
    ).toBeInTheDocument();
  });

  it("searches lemmas and lists the matches", async () => {
    const results = [
      {
        id: "22222222-2222-2222-2222-222222222222",
        lemma: "хата",
        normalized_lemma: "хата",
        part_of_speech: "noun",
        key_tags: ["inanim"],
        is_standard: true,
        match_type: "word_form",
        matched_form: "хати",
        matched_form_morphology: "noun:inanim:f:v_rod",
      },
    ];
    const fetchMock = vi.fn((input: unknown) => {
      const url = String(input);
      if (url.includes("/lemmas?")) {
        return Promise.resolve(jsonResponse(200, results));
      }
      return Promise.resolve(jsonResponse(200, lexicon()));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/reference-lexicons/vesum");

    const input = await screen.findByLabelText("Пошук леми або словоформи");
    fireEvent.change(input, { target: { value: "хат" } });

    expect(await screen.findByText("хата")).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText(/noun:inanim:f:v_rod/)).toBeInTheDocument(),
    );
  });
});
