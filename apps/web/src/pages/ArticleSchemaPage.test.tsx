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
    presentation_formula: "**{{ headword }}**",
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

  it("shows a past version's field tree in the viewer", async () => {
    const only = schema({
      version: 1,
      definition: {
        fields: [{ name: "unikalne_pole", role: "other", type: "string" }],
      },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [only])));

    renderAt(`/dictionaries/${DICTIONARY_ID}/article-schema`);

    fireEvent.click(await screen.findByRole("button", { name: "Переглянути" }));

    expect(
      await screen.findByRole("heading", { name: "Версія 1" }),
    ).toBeInTheDocument();
    expect(screen.getByText("unikalne_pole")).toBeInTheDocument();
  });

  it("edits a version and saves it as a new version", async () => {
    const v1 = schema({ version: 1 });
    const v2 = schema({
      id: "44444444-4444-4444-4444-444444444444",
      version: 2,
    });
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      if ((init?.method ?? "GET") === "POST") {
        return Promise.resolve(jsonResponse(201, v2));
      }
      return Promise.resolve(jsonResponse(200, fetchMock.mock.calls.length > 2 ? [v1, v2] : [v1]));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderAt(`/dictionaries/${DICTIONARY_ID}/article-schema`);

    fireEvent.click(await screen.findByRole("button", { name: "Редагувати" }));
    fireEvent.click(
      await screen.findByRole("button", { name: "Зберегти як нову версію" }),
    );

    await waitFor(() =>
      expect(screen.getByText(/Версію 2 збережено/)).toBeInTheDocument(),
    );
    const postCall = fetchMock.mock.calls.find(
      (call) => (call[1]?.method ?? "GET") === "POST",
    );
    expect(postCall?.[0]).toContain("/article-schemas");
  });

  it("round-trips a presentation formula through the editor", async () => {
    const FORMULA = "### {{ headword }} — {{ meaning }}";
    const v1 = schema({ version: 1 });
    const v2 = schema({
      id: "44444444-4444-4444-4444-444444444444",
      version: 2,
      presentation_formula: FORMULA,
    });
    const fetchMock = vi
      .fn()
      .mockImplementation((_url: string, init?: RequestInit) => {
        if ((init?.method ?? "GET") === "POST") {
          return Promise.resolve(jsonResponse(201, v2));
        }
        return Promise.resolve(
          jsonResponse(200, fetchMock.mock.calls.length > 2 ? [v1, v2] : [v1]),
        );
      });
    vi.stubGlobal("fetch", fetchMock);

    renderAt(`/dictionaries/${DICTIONARY_ID}/article-schema`);

    fireEvent.click(await screen.findByRole("button", { name: "Редагувати" }));
    fireEvent.change(await screen.findByLabelText(/Формула подання/), {
      target: { value: FORMULA },
    });
    fireEvent.click(
      screen.getByRole("button", { name: "Зберегти як нову версію" }),
    );

    await waitFor(() =>
      expect(screen.getByText(/Версію 2 збережено/)).toBeInTheDocument(),
    );
    const postCall = fetchMock.mock.calls.find(
      (call) => (call[1]?.method ?? "GET") === "POST",
    );
    const body = JSON.parse((postCall![1] as RequestInit).body as string);
    expect(body.presentation_formula).toBe(FORMULA);
    // and the saved version's formula is shown back in the viewer
    expect(await screen.findByText(FORMULA)).toBeInTheDocument();
  });

  it("blocks saving a version with no presentation formula", async () => {
    const v1 = schema({ version: 1, presentation_formula: "" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, [v1])),
    );

    renderAt(`/dictionaries/${DICTIONARY_ID}/article-schema`);

    fireEvent.click(await screen.findByRole("button", { name: "Редагувати" }));
    fireEvent.click(
      screen.getByRole("button", { name: "Зберегти як нову версію" }),
    );

    expect(
      await screen.findByText("Додайте формулу подання статті."),
    ).toBeInTheDocument();
  });

  it("shows a removed field when comparing two versions", async () => {
    const v1 = schema({
      version: 1,
      definition: {
        fields: [
          { name: "meaning", role: "meaning", type: "string" },
          { name: "example", role: "example", type: "string" },
        ],
      },
    });
    const v2 = schema({
      id: "55555555-5555-5555-5555-555555555555",
      version: 2,
      definition: { fields: [{ name: "meaning", role: "meaning", type: "string" }] },
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [v1, v2])));

    renderAt(`/dictionaries/${DICTIONARY_ID}/article-schema`);

    expect(
      await screen.findByRole("heading", { name: "Порівняння версій" }),
    ).toBeInTheDocument();
    expect(screen.getByText("example")).toBeInTheDocument();
    expect(screen.getByText("вилучено")).toBeInTheDocument();
  });
});
