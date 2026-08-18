import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { LexemeResponse } from "../api";
import type { LexemesForPageState } from "../hooks/useLexemesForPage";
import { LexemeList } from "./LexemeList";

function lexemeFixture(overrides: Partial<LexemeResponse> = {}): LexemeResponse {
  return {
    id: "lex-1",
    dictionary_id: "dict-1",
    page_id: "page-1",
    source_text: "слово",
    x: 100,
    y: 120,
    width: 200,
    height: 80,
    origin: "manual",
    created_at: "2026-08-18T00:00:00Z",
    created_by: "user-1",
    updated_at: "2026-08-18T00:00:00Z",
    updated_by: "user-1",
    ...overrides,
  };
}

describe("LexemeList", () => {
  it("shows a loading indicator", () => {
    render(
      <LexemeList
        lexemesState={{ status: "loading" }}
        pageNumber={1}
        selectedLexemeId={null}
        onSelectLexeme={vi.fn()}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Завантажуємо лексеми");
  });

  it("shows an error message", () => {
    const state: LexemesForPageState = { status: "error", message: "Проблема" };
    render(
      <LexemeList
        lexemesState={state}
        pageNumber={1}
        selectedLexemeId={null}
        onSelectLexeme={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Проблема");
  });

  it("explains an empty page", () => {
    render(
      <LexemeList
        lexemesState={{ status: "loaded", lexemes: [] }}
        pageNumber={1}
        selectedLexemeId={null}
        onSelectLexeme={vi.fn()}
      />,
    );
    expect(screen.getByText(/ще немає виділених лексем/)).toBeInTheDocument();
  });

  it("lists each lexeme's text, page number, and bounding box (AC2)", () => {
    render(
      <LexemeList
        lexemesState={{
          status: "loaded",
          lexemes: [lexemeFixture({ x: 100.4, y: 120.6, width: 200, height: 80 })],
        }}
        pageNumber={3}
        selectedLexemeId={null}
        onSelectLexeme={vi.fn()}
      />,
    );

    expect(screen.getByText("слово")).toBeInTheDocument();
    const item = screen.getByRole("button");
    expect(item).toHaveTextContent("Сторінка 3");
    expect(item).toHaveTextContent("x=100, y=121");
    expect(item).toHaveTextContent("200×80");
  });

  it("calls onSelectLexeme when a row is clicked (AC3)", () => {
    const onSelectLexeme = vi.fn();
    render(
      <LexemeList
        lexemesState={{ status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] }}
        pageNumber={1}
        selectedLexemeId={null}
        onSelectLexeme={onSelectLexeme}
      />,
    );

    fireEvent.click(screen.getByRole("button"));

    expect(onSelectLexeme).toHaveBeenCalledWith("lex-7");
  });

  it("marks the selected lexeme's row (AC3)", () => {
    render(
      <LexemeList
        lexemesState={{ status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] }}
        pageNumber={1}
        selectedLexemeId="lex-7"
        onSelectLexeme={vi.fn()}
      />,
    );

    expect(screen.getByRole("button")).toHaveAttribute("aria-pressed", "true");
  });
});
