import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AbbreviationResponse } from "../api";
import { AbbreviationRowForm } from "./AbbreviationRowForm";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function existing(
  overrides: Partial<AbbreviationResponse> = {},
): AbbreviationResponse {
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

function renderRow(ui: React.ReactElement) {
  return render(
    <table>
      <tbody>{ui}</tbody>
    </table>,
  );
}

describe("AbbreviationRowForm", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("requires a full form unless the entry is marked unresolved (AC2)", async () => {
    renderRow(
      <AbbreviationRowForm
        dictionaryId={DICTIONARY_ID}
        editing={null}
        onDone={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Скорочення"), {
      target: { value: "заст." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    await waitFor(() =>
      expect(screen.getByText(/Вкажіть повну форму/)).toBeInTheDocument(),
    );
  });

  it("allows saving an unresolved entry without a full form (AC2)", async () => {
    const user = userEvent.setup();
    const created = existing({ unresolved: true, full_form: null });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(201, created)));
    const onDone = vi.fn();

    renderRow(
      <AbbreviationRowForm
        dictionaryId={DICTIONARY_ID}
        editing={null}
        onDone={onDone}
      />,
    );
    fireEvent.change(screen.getByLabelText("Скорочення"), {
      target: { value: "??" },
    });
    await user.click(screen.getByRole("combobox", { name: "Категорія" }));
    await user.click(screen.getByRole("option", { name: "Інше" }));
    fireEvent.click(screen.getByLabelText("Розшифрування поки невідоме"));
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    await waitFor(() => expect(onDone).toHaveBeenCalledWith(created));
  });

  it("splits the comma-separated variants field into an array on save", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(201, existing()));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    renderRow(
      <AbbreviationRowForm
        dictionaryId={DICTIONARY_ID}
        editing={null}
        onDone={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText("Скорочення"), {
      target: { value: "розм." },
    });
    await user.click(screen.getByRole("combobox", { name: "Категорія" }));
    await user.click(screen.getByRole("option", { name: "Вживання" }));
    fireEvent.change(screen.getByLabelText("Повна форма"), {
      target: { value: "розмовне" },
    });
    fireEvent.change(
      screen.getByLabelText("Варіанти написання (через кому)"),
      { target: { value: "розм; р. ,, розмовн" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const body = JSON.parse(
      (fetchMock.mock.calls.at(-1)?.[1] as RequestInit).body as string,
    );
    expect(body.variants).toEqual(["розм", "р.", "розмовн"]);
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
    renderRow(
      <AbbreviationRowForm
        dictionaryId={DICTIONARY_ID}
        editing={null}
        onDone={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByLabelText("Скорочення"), {
      target: { value: "розм." },
    });
    await user.click(screen.getByRole("combobox", { name: "Категорія" }));
    await user.click(screen.getByRole("option", { name: "Вживання" }));
    fireEvent.change(screen.getByLabelText("Повна форма"), {
      target: { value: "розмовне" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("вже існує"),
    );
  });

  it("pre-fills the row when editing an existing entry (AC3)", () => {
    renderRow(
      <AbbreviationRowForm
        dictionaryId={DICTIONARY_ID}
        editing={existing({ variants: ["р.", "розм"] })}
        onDone={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Скорочення")).toHaveValue("розм.");
    expect(screen.getByLabelText("Повна форма")).toHaveValue("розмовне");
    expect(
      screen.getByLabelText("Варіанти написання (через кому)"),
    ).toHaveValue("р., розм");
  });
});
