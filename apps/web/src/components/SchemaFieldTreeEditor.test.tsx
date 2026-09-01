import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ArticleSchemaResponse } from "../api";
import { useArticleSchemaEditor } from "../hooks/useArticleSchemaEditor";
import { SchemaFieldTreeEditor } from "./SchemaFieldTreeEditor";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** An `initial` that seeds only the (now-required) presentation formula --
 * `definition.fields` stays empty, so the field-tree behaves as if starting
 * from scratch. */
const FORMULA_ONLY = {
  definition: { fields: [] },
  presentation_formula: "{{ headword }}",
  source_description: "",
} as unknown as ArticleSchemaResponse;

function Harness({
  initial = FORMULA_ONLY,
  onSaved = vi.fn(),
}: {
  initial?: ArticleSchemaResponse | null;
  onSaved?: (saved: ArticleSchemaResponse) => void;
}) {
  const editor = useArticleSchemaEditor({
    dictionaryId: DICTIONARY_ID,
    initial,
    onSaved,
  });
  return (
    <>
      <SchemaFieldTreeEditor editor={editor} />
      <button type="button" onClick={() => void editor.submit()}>
        Зберегти
      </button>
      {editor.rootError && <p role="alert">{editor.rootError}</p>}
    </>
  );
}

describe("SchemaFieldTreeEditor", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("adds and removes a field", () => {
    render(<Harness />);
    expect(screen.getByText(/Полів ще немає/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Додати поле" }));
    fireEvent.change(screen.getByLabelText("Назва поля (рівень 1)"), {
      target: { value: "meaning" },
    });
    expect(screen.getByLabelText("Назва поля (рівень 1)")).toHaveValue("meaning");

    fireEvent.click(screen.getByRole("button", { name: "Видалити поле" }));
    expect(
      screen.queryByLabelText("Назва поля (рівень 1)"),
    ).not.toBeInTheDocument();
  });

  it("blocks saving an empty schema", async () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    await waitFor(() =>
      expect(screen.getByText("Додайте щонайменше одне поле.")).toBeInTheDocument(),
    );
  });

  it("posts a normalized definition built from the edited tree", async () => {
    const created: ArticleSchemaResponse = {
      id: "22222222-2222-2222-2222-222222222222",
      dictionary_id: DICTIONARY_ID,
      version: 2,
      status: "ready",
      source_description: "",
      definition: { fields: [] },
      provider_name: null,
      error_message: null,
      presentation_formula: null,
      created_at: "2026-08-20T10:00:00Z",
      activated_at: null,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, created));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    const onSaved = vi.fn();

    render(<Harness onSaved={onSaved} />);

    fireEvent.click(screen.getByRole("button", { name: "Додати поле" }));
    fireEvent.change(screen.getByLabelText("Назва поля (рівень 1)"), {
      target: { value: "meaning" },
    });
    await user.click(screen.getByRole("combobox", { name: "Роль поля (рівень 1)" }));
    await user.click(screen.getByRole("option", { name: "Значення" }));

    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(created));
    const body = JSON.parse(
      (fetchMock.mock.calls.at(-1)?.[1] as RequestInit).body as string,
    );
    expect(body.definition.fields).toEqual([
      {
        name: "meaning",
        role: "meaning",
        type: "string",
        options: [],
        repeatable: false,
        required: false,
        children: [],
      },
    ]);
  });

  it("captures enum options and blocks saving until one is added", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<Harness />);

    fireEvent.click(screen.getByRole("button", { name: "Додати поле" }));
    fireEvent.change(screen.getByLabelText("Назва поля (рівень 1)"), {
      target: { value: "gender" },
    });
    await user.click(screen.getByRole("combobox", { name: "Тип поля (рівень 1)" }));
    await user.click(screen.getByRole("option", { name: "Перелік" }));

    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    await waitFor(() =>
      expect(
        screen.getByText("Додайте щонайменше одне значення переліку."),
      ).toBeInTheDocument(),
    );
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Додати значення" }));
    fireEvent.change(screen.getByLabelText(/Значення переліку 1/), {
      target: { value: "ч." },
    });
    expect(
      screen.queryByText("Додайте щонайменше одне значення переліку."),
    ).not.toBeInTheDocument();
  });

  it("offers the reference field types without an options editor", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, {}));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Додати поле" }));
    fireEvent.change(screen.getByLabelText("Назва поля (рівень 1)"), {
      target: { value: "abbr" },
    });

    await user.click(screen.getByRole("combobox", { name: "Тип поля (рівень 1)" }));
    expect(
      screen.getByRole("option", { name: "Скорочення" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("option", { name: "Географічна мітка" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: "Скорочення" }));

    expect(
      screen.queryByRole("button", { name: "Додати значення" }),
    ).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = JSON.parse(
      (fetchMock.mock.calls.at(-1)?.[1] as RequestInit).body as string,
    );
    expect(body.definition.fields[0]).toMatchObject({
      type: "abbreviation",
      options: [],
    });
  });

  it("surfaces a server-side field error (422)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(422, {
          errors: { "fields[0].name": "Назва вже зайнята." },
        }),
      ),
    );

    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "Додати поле" }));
    fireEvent.change(screen.getByLabelText("Назва поля (рівень 1)"), {
      target: { value: "meaning" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    await waitFor(() =>
      expect(screen.getByText("Назва вже зайнята.")).toBeInTheDocument(),
    );
  });
});
