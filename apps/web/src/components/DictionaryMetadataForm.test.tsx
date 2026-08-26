import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DictionaryResponse } from "../api";
import { DictionaryMetadataForm } from "./DictionaryMetadataForm";

function baseDictionary(
  overrides: Partial<DictionaryResponse> = {},
): DictionaryResponse {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    status: "draft",
    title: null,
    description: null,
    article_description: null,
    dictionary_type: null,
    publisher: null,
    publication_year: null,
    edition: null,
    isbn: null,
    digital_source: null,
    legal_status: null,
    license_type: null,
    permission_reference: null,
    rights_note: null,
    contributors: [],
    language_codes: [],
    created_at: "2026-08-15T12:00:00Z",
    updated_at: "2026-08-15T12:00:00Z",
    missing_required_fields: ["title", "languages", "legal_status"],
    readiness_blockers: [],
    source: null,
    ...overrides,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("DictionaryMetadataForm", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows which required fields are still missing", () => {
    render(<DictionaryMetadataForm initialDictionary={baseDictionary()} />);

    expect(screen.getByRole("status", { name: "" })).toHaveTextContent(
      /Назва.*Мови.*Правовий статус/,
    );
  });

  it("adds, edits, reorders, and removes contributors", () => {
    render(<DictionaryMetadataForm initialDictionary={baseDictionary()} />);

    fireEvent.click(screen.getByRole("button", { name: "Додати автора чи укладача" }));
    fireEvent.click(screen.getByRole("button", { name: "Додати автора чи укладача" }));
    const [firstInput, secondInput] = screen.getAllByLabelText("Ім'я");
    fireEvent.change(firstInput as HTMLElement, {
      target: { value: "Борис Грінченко" },
    });
    fireEvent.change(secondInput as HTMLElement, {
      target: { value: "Марія Загірня" },
    });

    expect(
      screen.getAllByLabelText("Ім'я").map((el) => (el as HTMLInputElement).value),
    ).toEqual(["Борис Грінченко", "Марія Загірня"]);

    fireEvent.click(
      screen.getByRole("button", { name: "Перемістити Марія Загірня вище" }),
    );
    expect(
      screen.getAllByLabelText("Ім'я").map((el) => (el as HTMLInputElement).value),
    ).toEqual(["Марія Загірня", "Борис Грінченко"]);

    fireEvent.click(
      screen.getByRole("button", { name: "Видалити Марія Загірня" }),
    );
    expect(screen.getAllByLabelText("Ім'я")).toHaveLength(1);
    expect((screen.getByLabelText("Ім'я") as HTMLInputElement).value).toBe(
      "Борис Грінченко",
    );
  });

  it("supports selecting multiple languages", () => {
    render(<DictionaryMetadataForm initialDictionary={baseDictionary()} />);

    fireEvent.click(screen.getByLabelText("Українська"));
    fireEvent.click(screen.getByLabelText("English"));

    expect(screen.getByLabelText("Українська")).toBeChecked();
    expect(screen.getByLabelText("English")).toBeChecked();
  });

  it("only shows conditional legal fields for the relevant status", () => {
    render(<DictionaryMetadataForm initialDictionary={baseDictionary()} />);

    expect(screen.queryByLabelText("Тип ліцензії")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Правовий статус"), {
      target: { value: "licensed" },
    });
    expect(screen.getByLabelText("Тип ліцензії")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Правовий статус"), {
      target: { value: "permission_granted" },
    });
    expect(screen.queryByLabelText("Тип ліцензії")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Ідентифікатор чи опис дозволу")).toBeInTheDocument();
  });

  it("validates publication year and ISBN on blur", async () => {
    render(<DictionaryMetadataForm initialDictionary={baseDictionary()} />);

    fireEvent.change(screen.getByLabelText("Рік видання"), {
      target: { value: "999" },
    });
    fireEvent.blur(screen.getByLabelText("Рік видання"));
    await waitFor(() =>
      expect(screen.getByText(/Рік видання має бути в межах/)).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByLabelText("ISBN"), {
      target: { value: "0306406153" },
    });
    fireEvent.blur(screen.getByLabelText("ISBN"));
    await waitFor(() =>
      expect(
        screen.getByText(/Некоректна контрольна сума ISBN-10/),
      ).toBeInTheDocument(),
    );
  });

  it("saves the draft and reflects the server's missing-field list", async () => {
    const saved = baseDictionary({
      title: "Словник",
      language_codes: ["uk"],
      legal_status: "public_domain",
      missing_required_fields: [],
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, saved)));

    render(<DictionaryMetadataForm initialDictionary={baseDictionary()} />);
    fireEvent.change(screen.getByLabelText("Назва"), {
      target: { value: "Словник" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти чернетку" }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Усі обов'язкові поля"),
    );
    expect(screen.queryByText(/Ще не заповнено/)).not.toBeInTheDocument();
  });

  it("maps field-level errors returned by the server", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(422, { errors: { isbn: "Некоректна контрольна сума ISBN-10." } }),
      ),
    );

    render(<DictionaryMetadataForm initialDictionary={baseDictionary()} />);
    fireEvent.click(screen.getByRole("button", { name: "Зберегти чернетку" }));

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Перевірте поля"),
    );
  });

  it("pre-fills the form when editing an existing dictionary", () => {
    const existing = baseDictionary({
      title: "Наявний словник",
      legal_status: "public_domain",
      language_codes: ["uk"],
      article_description: "Стаття містить значення, приклади та синоніми.",
    });

    render(<DictionaryMetadataForm initialDictionary={existing} source={null} />);

    expect(screen.getByLabelText("Назва")).toHaveValue("Наявний словник");
    expect(screen.getByLabelText("Українська")).toBeChecked();
    expect(screen.getByLabelText("Структура словникової статті")).toHaveValue(
      "Стаття містить значення, приклади та синоніми.",
    );
  });

  it("saves article_description alongside the rest of the metadata", async () => {
    const saved = baseDictionary({
      article_description: "Значення, приклади, синоніми.",
    });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, saved));
    vi.stubGlobal("fetch", fetchMock);

    render(<DictionaryMetadataForm initialDictionary={baseDictionary()} />);
    fireEvent.change(screen.getByLabelText("Структура словникової статті"), {
      target: { value: "Значення, приклади, синоніми." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти чернетку" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, requestInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(requestInit.body as string) as {
      article_description: string | null;
    };
    expect(body.article_description).toBe("Значення, приклади, синоніми.");
  });

  it("shows the already-uploaded source without offering to re-upload it", () => {
    const withSource = baseDictionary({
      source: {
        original_filename: "dictionary.pdf",
        mime_type: "application/pdf",
        byte_size: 2048,
        page_count: 5,
        checksum_sha256: "a".repeat(64),
        uploaded_at: "2026-08-15T12:00:00Z",
        inspection_status: "verified",
        pages_status: "completed",
      },
    });

    render(
      <DictionaryMetadataForm initialDictionary={withSource} source={withSource.source} />,
    );

    expect(screen.getByText(/dictionary\.pdf/)).toBeInTheDocument();
    expect(screen.queryByLabelText("PDF-файл")).not.toBeInTheDocument();
  });
});
