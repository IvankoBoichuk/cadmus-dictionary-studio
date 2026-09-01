import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthenticatedUser, EntryResponse } from "../api";
import { AuthContext, type AuthContextValue } from "../authContext";
import { EntryDetailPage } from "./EntryDetailPage";

const ENTRY_ID = "33333333-3333-3333-3333-333333333333";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/**
 * Routes `fetch` by URL + method. The three GETs the page issues on mount
 * (the entry, its article schemas, its reference links) are answered from
 * `page` regardless of order; every other call is taken from `actions` in
 * call order, then falls back to an empty `200`.
 */
function stubFetch(
  page: { entry: unknown; schemas?: unknown; links?: unknown },
  actions: Array<() => Response> = [],
) {
  const queue = [...actions];
  const mock = vi.fn((input: unknown, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (method === "GET") {
      if (/\/article-schemas(\?|$)/.test(url)) {
        return Promise.resolve(jsonResponse(200, page.schemas ?? []));
      }
      if (url.endsWith("/reference-links")) {
        return Promise.resolve(jsonResponse(200, page.links ?? []));
      }
      if (/\/entries\/[^/]+$/.test(url)) {
        return Promise.resolve(jsonResponse(200, page.entry));
      }
    }
    const next = queue.shift();
    return Promise.resolve(next ? next() : jsonResponse(200, []));
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

function postCallBody(mock: ReturnType<typeof stubFetch>): unknown {
  const call = mock.mock.calls.find(
    ([, init]) => (init as RequestInit | undefined)?.method === "POST",
  );
  if (!call) throw new Error("no POST request was made");
  return JSON.parse((call[1] as RequestInit).body as string);
}

function authenticated(): AuthContextValue {
  return {
    session: { status: "authenticated", user: {} as AuthenticatedUser },
    setAuthenticated: vi.fn(),
    setAnonymous: vi.fn(),
  };
}

function baseEntry(overrides: Partial<EntryResponse> = {}): EntryResponse {
  return {
    id: ENTRY_ID,
    dictionary_id: "11111111-1111-1111-1111-111111111111",
    lexeme_id: "44444444-4444-4444-4444-444444444444",
    headword: "слово",
    status: "draft",
    schema_id: null,
    created_at: "2026-08-15T12:00:00Z",
    updated_at: "2026-08-15T12:00:00Z",
    fragments: [
      {
        id: "55555555-5555-5555-5555-555555555555",
        page_id: "66666666-6666-6666-6666-666666666666",
        page_number: 3,
        x: 0,
        y: 0,
        width: 10,
        height: 10,
        x2: null,
        y2: null,
        width2: null,
        height2: null,
        reading_order: 0,
        recognized_text: "слово - значення",
      },
    ],
    fields: [
      {
        id: "77777777-7777-7777-7777-777777777777",
        fragment_id: "55555555-5555-5555-5555-555555555555",
        parent_field_id: null,
        field_path: "meaning",
        role: "meaning",
        position: 0,
        source_text: "значення",
        source_start: 8,
        source_end: 16,
        x: null,
        y: null,
        width: null,
        height: null,
        normalized_text: null,
        confidence: 0.9,
        origin: "model",
        created_at: "2026-08-15T12:00:00Z",
        updated_at: "2026-08-15T12:00:00Z",
      },
    ],
    ...overrides,
  };
}

function renderAt(path: string) {
  return render(
    <AuthContext.Provider value={authenticated()}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/entries/:entryId" element={<EntryDetailPage />} />
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("EntryDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the headword, status, source fragment, and fields grouped by role", async () => {
    stubFetch({ entry: baseEntry() });

    renderAt(`/entries/${ENTRY_ID}`);

    expect(await screen.findByText("слово")).toBeInTheDocument();
    expect(screen.getByText("Чернетка")).toBeInTheDocument();
    expect(screen.getByText("слово - значення")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Значення", level: 3 })).toBeInTheDocument();
    expect(screen.getByText("значення")).toBeInTheDocument();
  });

  it("edits a field and reflects the saved value", async () => {
    const entry = baseEntry();
    const updatedField = { ...entry.fields[0], normalized_text: "нове значення" };
    stubFetch({ entry }, [() => jsonResponse(200, updatedField)]);

    renderAt(`/entries/${ENTRY_ID}`);
    await screen.findByText("значення");

    fireEvent.click(screen.getByRole("button", { name: "Редагувати" }));
    const input = screen.getByDisplayValue("значення");
    fireEvent.change(input, { target: { value: "нове значення" } });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    expect(await screen.findByText("нове значення")).toBeInTheDocument();
  });

  it("deletes a field after confirmation", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    stubFetch({ entry: baseEntry() }, [
      () => new Response(null, { status: 204 }),
    ]);

    renderAt(`/entries/${ENTRY_ID}`);
    await screen.findByText("значення");

    fireEvent.click(screen.getByRole("button", { name: "Видалити" }));

    await waitFor(() =>
      expect(screen.getByText("Полів ще немає — запустіть автоматичний розбір.")).toBeInTheDocument(),
    );
  });

  it("marks the entry complete on success", async () => {
    const entry = baseEntry();
    const completed = { ...entry, status: "complete" as const };
    stubFetch({ entry }, [() => jsonResponse(200, completed)]);

    renderAt(`/entries/${ENTRY_ID}`);
    await screen.findByText("слово");

    fireEvent.click(screen.getByRole("button", { name: "Позначити завершеною" }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("завершеною"),
    );
    expect(screen.getByText("Завершено")).toBeInTheDocument();
  });

  it("surfaces validation errors when completion is rejected", async () => {
    stubFetch({ entry: baseEntry() }, [
      () =>
        jsonResponse(422, { errors: { headword: "Бракує обов'язкового поля." } }),
    ]);

    renderAt(`/entries/${ENTRY_ID}`);
    await screen.findByText("слово");

    fireEvent.click(screen.getByRole("button", { name: "Позначити завершеною" }));

    expect(await screen.findByText("Бракує обов'язкового поля.")).toBeInTheDocument();
  });

  it("runs extraction and reports how many fields were created", async () => {
    const entry = baseEntry({ fields: [] });
    stubFetch({ entry }, [
      () => jsonResponse(202, { task_id: "task-1", status: "queued" }),
      () =>
        jsonResponse(200, {
          task_id: "task-1",
          status: "succeeded",
          created_fields: 2,
        }),
    ]);

    renderAt(`/entries/${ENTRY_ID}`);
    await screen.findByText("Полів ще немає — запустіть автоматичний розбір.");

    fireEvent.click(screen.getByRole("button", { name: "Розпізнати структуру" }));

    await waitFor(
      () => expect(screen.getByRole("status")).toHaveTextContent("Знайдено полів: 2"),
      { timeout: 3000 },
    );
  });

  it("renders a crop of the source page for each fragment", async () => {
    stubFetch({ entry: baseEntry() });

    renderAt(`/entries/${ENTRY_ID}`);
    await screen.findByText("слово");

    const crop = screen.getByAltText(/Скан сторінки 3/);
    expect(crop.getAttribute("src")).toContain("/dictionaries/11111111-1111-1111-1111-111111111111/pages/3");
  });

  it("adds a field manually using the dictionary's active article schema", async () => {
    const entry = baseEntry();
    const schema = {
      id: "88888888-8888-8888-8888-888888888888",
      dictionary_id: entry.dictionary_id,
      version: 1,
      status: "ready" as const,
      source_description: "опис",
      definition: {
        fields: [
          {
            name: "part_of_speech",
            role: "part_of_speech",
            type: "string",
            repeatable: false,
            required: false,
            children: [],
          },
        ],
      },
      provider_name: "anthropic",
      error_message: null,
      created_at: "2026-08-15T12:00:00Z",
      activated_at: "2026-08-15T12:05:00Z",
    };
    const createdField = {
      id: "99999999-9999-9999-9999-999999999999",
      fragment_id: entry.fragments[0]!.id,
      parent_field_id: null,
      field_path: "part_of_speech",
      role: "part_of_speech",
      position: 1,
      source_text: "слово",
      source_start: 0,
      source_end: 5,
      x: null,
      y: null,
      width: null,
      height: null,
      normalized_text: null,
      confidence: null,
      origin: "manual",
      created_at: "2026-08-15T12:10:00Z",
      updated_at: "2026-08-15T12:10:00Z",
    };
    const fetchMock = stubFetch({ entry, schemas: [schema] }, [
      () => jsonResponse(201, createdField),
    ]);

    renderAt(`/entries/${ENTRY_ID}`);
    await screen.findByText("слово");

    fireEvent.click(
      screen.getByRole("button", { name: "Додати поле вручну" }),
    );
    const pathSelect = await screen.findByLabelText("Поле схеми");
    await waitFor(() =>
      expect(
        Array.from((pathSelect as HTMLSelectElement).options).some(
          (option) => option.value === "part_of_speech",
        ),
      ).toBe(true),
    );
    fireEvent.change(pathSelect, { target: { value: "part_of_speech" } });
    fireEvent.change(
      screen.getByLabelText("Текст поля (як він написаний у фрагменті)"),
      { target: { value: "слово" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Додати поле" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([, init]) => (init as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
    expect(postCallBody(fetchMock)).toMatchObject({
      fragment_id: entry.fragments[0]!.id,
      field_path: "part_of_speech",
      role: "part_of_speech",
      source_text: "слово",
      source_start: 0,
      source_end: 5,
    });
  });

  it("offers a dropdown of enum options for an enum schema field", async () => {
    const entry = baseEntry();
    const schema = {
      id: "88888888-8888-8888-8888-888888888888",
      dictionary_id: entry.dictionary_id,
      version: 1,
      status: "ready" as const,
      source_description: "опис",
      definition: {
        fields: [
          {
            name: "gender",
            role: "other",
            type: "enum",
            options: ["ч.", "ж.", "с."],
            repeatable: false,
            required: false,
            children: [],
          },
        ],
      },
      provider_name: "anthropic",
      error_message: null,
      created_at: "2026-08-15T12:00:00Z",
      activated_at: "2026-08-15T12:05:00Z",
    };
    const createdField = {
      id: "99999999-9999-9999-9999-999999999999",
      fragment_id: entry.fragments[0]!.id,
      parent_field_id: null,
      field_path: "gender",
      role: "other",
      position: 1,
      source_text: "ж.",
      source_start: 0,
      source_end: 0,
      x: null,
      y: null,
      width: null,
      height: null,
      normalized_text: null,
      confidence: null,
      origin: "manual",
      created_at: "2026-08-15T12:10:00Z",
      updated_at: "2026-08-15T12:10:00Z",
    };
    const fetchMock = stubFetch({ entry, schemas: [schema] }, [
      () => jsonResponse(201, createdField),
    ]);

    renderAt(`/entries/${ENTRY_ID}`);
    await screen.findByText("слово");

    fireEvent.click(screen.getByRole("button", { name: "Додати поле вручну" }));
    const pathSelect = await screen.findByLabelText("Поле схеми");
    await waitFor(() =>
      expect(
        Array.from((pathSelect as HTMLSelectElement).options).some(
          (option) => option.value === "gender",
        ),
      ).toBe(true),
    );
    fireEvent.change(pathSelect, { target: { value: "gender" } });

    const valueSelect = (await screen.findByLabelText(
      "Значення",
    )) as HTMLSelectElement;
    expect(
      Array.from(valueSelect.options).map((option) => option.value),
    ).toEqual(["", "ч.", "ж.", "с."]);

    fireEvent.change(valueSelect, { target: { value: "ж." } });
    fireEvent.click(screen.getByRole("button", { name: "Додати поле" }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          ([, init]) => (init as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
    expect(postCallBody(fetchMock)).toMatchObject({
      field_path: "gender",
      source_text: "ж.",
    });
  });

  it("flattens a nested schema whose leaf nodes omit `children` entirely without hanging", async () => {
    // Regression test: real AI-generated schemas often omit `children` on
    // leaf nodes rather than setting it to `[]`. A recursive flatten that
    // relies on a default parameter for the recursive-call argument
    // resolves that `undefined` back to the *top-level* field list,
    // silently restarting the walk from the root forever.
    const entry = baseEntry();
    const schema = {
      id: "88888888-8888-8888-8888-888888888888",
      dictionary_id: entry.dictionary_id,
      version: 1,
      status: "ready" as const,
      source_description: "опис",
      definition: {
        fields: [
          {
            name: "grammatical_info",
            role: "other",
            type: "group",
            repeatable: false,
            required: false,
            children: [
              {
                name: "usual_plural_form",
                role: "other",
                type: "group",
                repeatable: false,
                required: false,
                children: [
                  { name: "label", role: "abbreviation", type: "string" },
                ],
              },
            ],
          },
        ],
      },
      provider_name: "anthropic",
      error_message: null,
      created_at: "2026-08-15T12:00:00Z",
      activated_at: "2026-08-15T12:05:00Z",
    };
    stubFetch({ entry, schemas: [schema] });

    renderAt(`/entries/${ENTRY_ID}`);
    await screen.findByText("слово");

    fireEvent.click(
      screen.getByRole("button", { name: "Додати поле вручну" }),
    );
    const pathSelect = await screen.findByLabelText("Поле схеми");
    await waitFor(() =>
      expect(
        Array.from((pathSelect as HTMLSelectElement).options).map(
          (option) => option.value,
        ),
      ).toEqual(["grammatical_info", "usual_plural_form", "label", "custom"]),
    );
  });
});
