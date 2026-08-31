import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AbbreviationResponse } from "../api";
import { AbbreviationForm } from "./AbbreviationForm";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function existing(overrides: Partial<AbbreviationResponse> = {}): AbbreviationResponse {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    abbreviation: "розм.",
    category: "usage",
    full_form: "розмовне",
    language_code: "uk",
    note: null,
    unresolved: false,
    variants: [],
    created_at: "2026-08-16T12:00:00Z",
    updated_at: "2026-08-16T12:00:00Z",
    ...overrides,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("AbbreviationForm", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requires a full form unless the entry is marked unresolved (AC2)", async () => {
    render(
      <AbbreviationForm dictionaryId={DICTIONARY_ID} editing={null} onSaved={vi.fn()} />,
    );

    fireEvent.change(screen.getByLabelText("Скорочення"), {
      target: { value: "заст." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Додати" }));

    await waitFor(() =>
      expect(screen.getByText(/Вкажіть повну форму/)).toBeInTheDocument(),
    );
  });

  it("allows saving an unresolved entry without a full form (AC2)", async () => {
    const user = userEvent.setup();
    const created = existing({ unresolved: true, full_form: null });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(201, created)));
    const onSaved = vi.fn();

    render(
      <AbbreviationForm dictionaryId={DICTIONARY_ID} editing={null} onSaved={onSaved} />,
    );
    fireEvent.change(screen.getByLabelText("Скорочення"), {
      target: { value: "??" },
    });
    await user.click(screen.getByRole("combobox", { name: "Категорія" }));
    await user.click(screen.getByRole("option", { name: "Інше" }));
    fireEvent.click(
      screen.getByLabelText("Розшифрування поки невідоме (нерозшифрований запис)"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Додати" }));

    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(created));
  });

  it("adds and removes spelling variants", () => {
    render(
      <AbbreviationForm dictionaryId={DICTIONARY_ID} editing={null} onSaved={vi.fn()} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Додати варіант написання" }));
    fireEvent.change(screen.getByLabelText("Варіант написання"), {
      target: { value: "розм" },
    });
    expect(screen.getByLabelText("Варіант написання")).toHaveValue("розм");

    fireEvent.click(screen.getByRole("button", { name: /Видалити варіант/ }));
    expect(screen.queryByLabelText("Варіант написання")).not.toBeInTheDocument();
  });

  it("surfaces a duplicate warning from the server (AC4)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(409, {
          code: "duplicate_abbreviation",
          abbreviation_id: "33333333-3333-3333-3333-333333333333",
          message: "Таке скорочення вже існує в цьому словнику.",
        }),
      ),
    );

    const user = userEvent.setup();
    render(
      <AbbreviationForm dictionaryId={DICTIONARY_ID} editing={null} onSaved={vi.fn()} />,
    );
    fireEvent.change(screen.getByLabelText("Скорочення"), {
      target: { value: "розм." },
    });
    await user.click(screen.getByRole("combobox", { name: "Категорія" }));
    await user.click(screen.getByRole("option", { name: "Вживання" }));
    fireEvent.change(screen.getByLabelText("Повна форма"), {
      target: { value: "розмовне" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Додати" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("вже існує"),
    );
  });

  it("pre-fills the form when editing an existing entry (AC3)", () => {
    const editing = existing({ variants: ["р.", "розм"] });

    render(
      <AbbreviationForm dictionaryId={DICTIONARY_ID} editing={editing} onSaved={vi.fn()} />,
    );

    expect(screen.getByLabelText("Скорочення")).toHaveValue("розм.");
    expect(screen.getByLabelText("Повна форма")).toHaveValue("розмовне");
    expect(screen.getAllByLabelText("Варіант написання")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Зберегти зміни" })).toBeInTheDocument();
  });
});
