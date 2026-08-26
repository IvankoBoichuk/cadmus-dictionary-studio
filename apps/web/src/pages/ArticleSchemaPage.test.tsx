import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ArticleSchemaResponse, AuthenticatedUser } from "../api";
import { AuthContext, type AuthContextValue } from "../authContext";
import { ArticleSchemaPage } from "./ArticleSchemaPage";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

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

function schema(overrides: Partial<ArticleSchemaResponse> = {}): ArticleSchemaResponse {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    dictionary_id: DICTIONARY_ID,
    version: 1,
    status: "ready",
    source_description: "Стаття містить значення, приклади та синоніми.",
    definition: { fields: [{ name: "meaning", role: "meaning", type: "string" }] },
    provider_name: "anthropic:claude-opus-5",
    error_message: null,
    created_at: "2026-08-15T12:00:00Z",
    activated_at: null,
    ...overrides,
  };
}

function renderAt(path: string) {
  return render(
    <AuthContext.Provider value={authenticated()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/dictionaries/:dictionaryId/article-schema"
            element={<ArticleSchemaPage />}
          />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("ArticleSchemaPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows a message when no schema versions exist yet", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [])));

    renderAt(`/dictionaries/${DICTIONARY_ID}/article-schema`);

    expect(await screen.findByText("Схему ще не генерували.")).toBeInTheDocument();
  });

  it("generates a schema and reports success once the task succeeds", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, []))
      .mockResolvedValueOnce(jsonResponse(202, { task_id: "task-1", status: "queued" }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          task_id: "task-1",
          status: "succeeded",
          schema_id: "22222222-2222-2222-2222-222222222222",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    renderAt(`/dictionaries/${DICTIONARY_ID}/article-schema`);
    await screen.findByText("Схему ще не генерували.");

    fireEvent.click(screen.getByRole("button", { name: "Згенерувати схему" }));

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Генеруємо схему…" }),
      ).toBeDisabled(),
    );

    await waitFor(
      () =>
        expect(screen.getByRole("status")).toHaveTextContent("Схему згенеровано"),
      { timeout: 3000 },
    );
  });

  it("activates a ready, unactivated schema version", async () => {
    const readySchema = schema();
    const activatedSchema = schema({ activated_at: "2026-08-16T09:00:00Z" });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, [readySchema]))
      .mockResolvedValueOnce(jsonResponse(200, activatedSchema))
      .mockResolvedValueOnce(jsonResponse(200, [activatedSchema]));
    vi.stubGlobal("fetch", fetchMock);

    renderAt(`/dictionaries/${DICTIONARY_ID}/article-schema`);
    await screen.findByRole("button", { name: "Активувати" });

    fireEvent.click(screen.getByRole("button", { name: "Активувати" }));

    await waitFor(() => expect(screen.getByText(/активна/)).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Активувати" })).not.toBeInTheDocument();
  });
});
