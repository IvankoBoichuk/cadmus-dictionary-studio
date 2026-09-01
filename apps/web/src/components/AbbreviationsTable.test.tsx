import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AbbreviationResponse } from "../api";
import { AbbreviationsTable } from "./AbbreviationsTable";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function row(overrides: Partial<AbbreviationResponse> = {}): AbbreviationResponse {
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

function renderTable(items: AbbreviationResponse[]) {
  return render(
    <AbbreviationsTable
      dictionaryId={DICTIONARY_ID}
      abbreviations={items}
      onSaved={vi.fn()}
      onDelete={vi.fn()}
      deleteState={{}}
    />,
  );
}

describe("AbbreviationsTable", () => {
  it("shows an empty-state hint and the add button when there are no rows", () => {
    renderTable([]);
    expect(screen.getByText(/Скорочень ще немає/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Додати скорочення" }),
    ).toBeInTheDocument();
  });

  it("reveals the inline add-row form when the + button is clicked", () => {
    renderTable([]);
    fireEvent.click(screen.getByRole("button", { name: "Додати скорочення" }));

    expect(screen.getByLabelText("Скорочення")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Зберегти" })).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Додати скорочення" }),
    ).not.toBeInTheDocument();
  });

  it("swaps a data row for the inline form when the edit action is used", () => {
    renderTable([row()]);
    expect(screen.queryByLabelText("Скорочення")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Редагувати" }));

    expect(screen.getByLabelText("Скорочення")).toHaveValue("розм.");
  });

  it("exposes accessible names on the icon-only row actions", () => {
    renderTable([row()]);
    expect(screen.getByRole("button", { name: "Редагувати" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Видалити" })).toBeInTheDocument();
  });
});
