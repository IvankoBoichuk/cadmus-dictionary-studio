import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LexemeResponse } from "../api";
import type { LexemesForPageState } from "../hooks/useLexemesForPage";
import type { UpdateLexemeState } from "../hooks/useUpdateLexeme";
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

const IDLE_UPDATE_STATE: UpdateLexemeState = { status: "idle" };

function renderList(
  overrides: Partial<{
    lexemesState: LexemesForPageState;
    pageNumber: number;
    selectedLexemeId: string | null;
    onSelectLexeme: (lexemeId: string) => void;
    redrawingLexemeId: string | null;
    onStartRedraw: (lexemeId: string) => void;
    onCancelRedraw: () => void;
    onSaveText: (lexemeId: string, text: string) => void;
    updateState: UpdateLexemeState;
    onDelete: (lexemeId: string) => void;
    secondBoxDraftLexemeId: string | null;
    onStartAddSecondBox: (lexemeId: string) => void;
    onCancelSecondBoxDraft: () => void;
    onRemoveSecondBox: (lexemeId: string) => void;
  }> = {},
) {
  return render(
    <LexemeList
      lexemesState={overrides.lexemesState ?? { status: "loaded", lexemes: [] }}
      pageNumber={overrides.pageNumber ?? 1}
      selectedLexemeId={overrides.selectedLexemeId ?? null}
      onSelectLexeme={overrides.onSelectLexeme ?? vi.fn()}
      redrawingLexemeId={overrides.redrawingLexemeId ?? null}
      onStartRedraw={overrides.onStartRedraw ?? vi.fn()}
      onCancelRedraw={overrides.onCancelRedraw ?? vi.fn()}
      onSaveText={overrides.onSaveText ?? vi.fn()}
      updateState={overrides.updateState ?? IDLE_UPDATE_STATE}
      onDelete={overrides.onDelete ?? vi.fn()}
      secondBoxDraftLexemeId={overrides.secondBoxDraftLexemeId ?? null}
      onStartAddSecondBox={overrides.onStartAddSecondBox ?? vi.fn()}
      onCancelSecondBoxDraft={overrides.onCancelSecondBoxDraft ?? vi.fn()}
      onRemoveSecondBox={overrides.onRemoveSecondBox ?? vi.fn()}
    />,
  );
}

describe("LexemeList", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a loading indicator", () => {
    renderList({ lexemesState: { status: "loading" } });
    expect(screen.getByRole("status")).toHaveTextContent("Завантажуємо лексеми");
  });

  it("shows an error message", () => {
    renderList({ lexemesState: { status: "error", message: "Проблема" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Проблема");
  });

  it("explains an empty page", () => {
    renderList({ lexemesState: { status: "loaded", lexemes: [] } });
    expect(screen.getByText(/ще немає виділених лексем/)).toBeInTheDocument();
  });

  it("lists each lexeme's text, page number, and bounding box (AC2)", () => {
    renderList({
      lexemesState: {
        status: "loaded",
        lexemes: [lexemeFixture({ x: 100.4, y: 120.6, width: 200, height: 80 })],
      },
      pageNumber: 3,
    });

    expect(screen.getByText("слово")).toBeInTheDocument();
    const item = screen.getByRole("button", { name: /слово/ });
    expect(item).toHaveTextContent("Сторінка 3");
    expect(item).toHaveTextContent("x=100, y=121");
    expect(item).toHaveTextContent("200×80");
  });

  it("calls onSelectLexeme when a row is clicked (AC3)", () => {
    const onSelectLexeme = vi.fn();
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] },
      onSelectLexeme,
    });

    fireEvent.click(screen.getByRole("button", { name: /слово/ }));

    expect(onSelectLexeme).toHaveBeenCalledWith("lex-7");
  });

  it("marks the selected lexeme's row (AC3)", () => {
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] },
      selectedLexemeId: "lex-7",
    });

    expect(screen.getByRole("button", { name: /слово/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("scrolls the selected lexeme's row into view (BH-70)", () => {
    const scrollIntoViewMock = vi.fn();
    vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(
      scrollIntoViewMock,
    );

    renderList({
      lexemesState: {
        status: "loaded",
        lexemes: [lexemeFixture({ id: "lex-1" }), lexemeFixture({ id: "lex-7" })],
      },
      selectedLexemeId: "lex-7",
    });

    expect(scrollIntoViewMock).toHaveBeenCalledWith(
      expect.objectContaining({ block: "nearest" }),
    );
  });

  it("edits text inline and saves it (BH-56 AC2, AC4)", () => {
    const onSaveText = vi.fn();
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] },
      onSaveText,
    });

    fireEvent.click(screen.getByRole("button", { name: "Редагувати текст" }));
    const input = screen.getByLabelText("Текст лексеми");
    fireEvent.change(input, { target: { value: "нове слово" } });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    expect(onSaveText).toHaveBeenCalledWith("lex-7", "нове слово");
    expect(screen.queryByLabelText("Текст лексеми")).not.toBeInTheDocument();
  });

  it("cancels text editing without saving", () => {
    const onSaveText = vi.fn();
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture()] },
      onSaveText,
    });

    fireEvent.click(screen.getByRole("button", { name: "Редагувати текст" }));
    fireEvent.change(screen.getByLabelText("Текст лексеми"), {
      target: { value: "скасовано" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Скасувати" }));

    expect(onSaveText).not.toHaveBeenCalled();
    expect(screen.getByText("слово")).toBeInTheDocument();
  });

  it("starts redraw mode for a lexeme (BH-56 AC3)", () => {
    const onStartRedraw = vi.fn();
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] },
      onStartRedraw,
    });

    fireEvent.click(screen.getByRole("button", { name: "Перемалювати область" }));

    expect(onStartRedraw).toHaveBeenCalledWith("lex-7");
  });

  it("offers to cancel redraw when already redrawing that lexeme", () => {
    const onCancelRedraw = vi.fn();
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] },
      redrawingLexemeId: "lex-7",
      onCancelRedraw,
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Скасувати перемальовування" }),
    );

    expect(onCancelRedraw).toHaveBeenCalled();
  });

  it("starts adding a second box for a lexeme without one", () => {
    const onStartAddSecondBox = vi.fn();
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] },
      onStartAddSecondBox,
    });

    fireEvent.click(screen.getByRole("button", { name: "Додати другу область" }));

    expect(onStartAddSecondBox).toHaveBeenCalledWith("lex-7");
  });

  it("offers to remove an existing second box instead of adding one", () => {
    const onRemoveSecondBox = vi.fn();
    renderList({
      lexemesState: {
        status: "loaded",
        lexemes: [lexemeFixture({ id: "lex-7", x2: 600, y2: 10, width2: 90, height2: 40 })],
      },
      onRemoveSecondBox,
    });

    expect(
      screen.queryByRole("button", { name: "Додати другу область" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Видалити другу область" }));

    expect(onRemoveSecondBox).toHaveBeenCalledWith("lex-7");
  });

  it("offers to cancel when already drafting a second box for that lexeme", () => {
    const onCancelSecondBoxDraft = vi.fn();
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] },
      secondBoxDraftLexemeId: "lex-7",
      onCancelSecondBoxDraft,
    });

    fireEvent.click(screen.getByRole("button", { name: "Скасувати другу область" }));

    expect(onCancelSecondBoxDraft).toHaveBeenCalled();
  });

  it("deletes a lexeme after confirmation (BH-56 AC1)", () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    const onDelete = vi.fn();
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture({ id: "lex-7" })] },
      onDelete,
    });

    fireEvent.click(screen.getByRole("button", { name: "Видалити" }));

    expect(onDelete).toHaveBeenCalledWith("lex-7");
  });

  it("does not delete when the confirmation is declined", () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const onDelete = vi.fn();
    renderList({
      lexemesState: { status: "loaded", lexemes: [lexemeFixture()] },
      onDelete,
    });

    fireEvent.click(screen.getByRole("button", { name: "Видалити" }));

    expect(onDelete).not.toHaveBeenCalled();
  });
});
