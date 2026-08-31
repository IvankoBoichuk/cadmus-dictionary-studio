import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LexemeResponse, LexemeSuggestion } from "../api";
import { LexemeCanvas } from "./LexemeCanvas";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubContainerRect() {
  vi.spyOn(HTMLDivElement.prototype, "getBoundingClientRect").mockReturnValue({
    x: 0,
    y: 0,
    left: 0,
    top: 0,
    right: 500,
    bottom: 700,
    width: 500,
    height: 700,
    toJSON: () => "",
  });
}

async function loadImage() {
  const image = await screen.findByAltText("Сторінка 1 з 1");
  Object.defineProperty(image, "naturalWidth", { value: 1000, configurable: true });
  Object.defineProperty(image, "naturalHeight", { value: 1400, configurable: true });
  fireEvent.load(image);
  return image;
}

function lexemeFixture(overrides: Partial<LexemeResponse> = {}): LexemeResponse {
  return {
    id: "lex-1",
    dictionary_id: "dict-1",
    page_id: "page-1",
    source_text: "слово",
    x: 100,
    y: 100,
    width: 200,
    height: 80,
    origin: "manual",
    status: "draft",
    created_at: "2026-08-18T00:00:00Z",
    created_by: "user-1",
    updated_at: "2026-08-18T00:00:00Z",
    updated_by: "user-1",
    ...overrides,
  };
}

function suggestionFixture(overrides: Partial<LexemeSuggestion> = {}): LexemeSuggestion {
  return {
    source_text: "розпізнане",
    x: 100,
    y: 100,
    width: 200,
    height: 80,
    confidence: 0.9,
    ...overrides,
  };
}

function renderCanvas(
  overrides: Partial<{
    lexemes: LexemeResponse[];
    onLexemeCreated: (lexeme: LexemeResponse) => void;
    selectedLexemeId: string | null;
    onSelectLexeme: (id: string | null) => void;
    redrawingLexemeId: string | null;
    onLexemeRedrawn: (lexeme: LexemeResponse) => void;
    onCancelRedraw: () => void;
    onSubmitUpdate: (
      lexemeId: string,
      input: { source_text: string; x: number; y: number; width: number; height: number },
    ) => Promise<LexemeResponse | null>;
    suggestions: LexemeSuggestion[];
    onAcceptSuggestion: (suggestion: LexemeSuggestion) => void;
    secondBoxDraftLexemeId: string | null;
    onSecondBoxDrawn: (lexeme: LexemeResponse) => void;
    onCancelSecondBoxDraft: () => void;
  }> = {},
) {
  return render(
    <LexemeCanvas
      dictionaryId="dict-1"
      pageNumber={1}
      imageUrl="/api/dictionaries/dict-1/pages/1"
      imageAlt="Сторінка 1 з 1"
      lexemes={overrides.lexemes ?? []}
      onLexemeCreated={overrides.onLexemeCreated ?? vi.fn()}
      selectedLexemeId={overrides.selectedLexemeId ?? null}
      onSelectLexeme={overrides.onSelectLexeme ?? vi.fn()}
      redrawingLexemeId={overrides.redrawingLexemeId ?? null}
      onLexemeRedrawn={overrides.onLexemeRedrawn ?? vi.fn()}
      onCancelRedraw={overrides.onCancelRedraw ?? vi.fn()}
      onSubmitUpdate={overrides.onSubmitUpdate ?? vi.fn().mockResolvedValue(null)}
      suggestions={overrides.suggestions}
      onAcceptSuggestion={overrides.onAcceptSuggestion}
      secondBoxDraftLexemeId={overrides.secondBoxDraftLexemeId ?? null}
      onSecondBoxDrawn={overrides.onSecondBoxDrawn}
      onCancelSecondBoxDraft={overrides.onCancelSecondBoxDraft}
    />,
  );
}

describe("LexemeCanvas", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("highlights the already-saved lexemes on the page (AC7)", async () => {
    stubContainerRect();

    renderCanvas({ lexemes: [lexemeFixture()] });
    await loadImage();

    expect(await screen.findByTitle("слово")).toBeInTheDocument();
  });

  it("marks the selected lexeme's box distinctly (BH-55)", async () => {
    stubContainerRect();

    renderCanvas({ lexemes: [lexemeFixture()], selectedLexemeId: "lex-1" });
    await loadImage();

    expect((await screen.findByTitle("слово")).className).toContain(
      "border-selected",
    );
  });

  it("draws a box and opens the text form on mouse up (AC1, AC2, AC3)", async () => {
    stubContainerRect();

    renderCanvas();
    const image = await loadImage();

    const canvas = image.parentElement as HTMLElement;
    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 150, clientY: 130 });
    fireEvent.mouseUp(canvas, { clientX: 150, clientY: 130 });

    expect(await screen.findByLabelText("Текст лексеми")).toBeInTheDocument();
  });

  it("submits the drawn box converted into natural page coordinates", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse(
        201,
        lexemeFixture({
          id: "lex-new",
          source_text: "нове",
          x: 100,
          y: 100,
          width: 200,
          height: 160,
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    stubContainerRect();
    const onLexemeCreated = vi.fn();
    const onSelectLexeme = vi.fn();

    renderCanvas({ onLexemeCreated, onSelectLexeme });
    const image = await loadImage();
    const canvas = image.parentElement as HTMLElement;

    // Container is 500x700 displayed, image natural size is 1000x1400 -> scale 2x.
    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 150, clientY: 130 });
    fireEvent.mouseUp(canvas, { clientX: 150, clientY: 130 });

    fireEvent.change(await screen.findByLabelText("Текст лексеми"), {
      target: { value: "нове" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти лексему" }));

    const createCall = await vi.waitFor(() => {
      const call = fetchMock.mock.calls[0];
      if (!call) throw new Error("expected a fetch call");
      return call;
    });
    const body = JSON.parse((createCall[1] as RequestInit).body as string);
    expect(body).toEqual({
      source_text: "нове",
      x: 100,
      y: 100,
      width: 200,
      height: 160,
      origin: "manual",
      confirm_duplicate: false,
    });
    await vi.waitFor(() => {
      expect(onLexemeCreated).toHaveBeenCalledWith(
        expect.objectContaining({ id: "lex-new" }),
      );
    });
    expect(onSelectLexeme).toHaveBeenCalledWith("lex-new");
  });

  it("offers to confirm and resubmit when the server reports a duplicate", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(409, {
          code: "duplicate_lexeme",
          existing_lexeme_id: "lex-existing",
          message: "Схожа лексема вже виділена на цій сторінці.",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(201, lexemeFixture({ id: "lex-confirmed", source_text: "нове" })),
      );
    vi.stubGlobal("fetch", fetchMock);
    stubContainerRect();

    renderCanvas();
    const image = await loadImage();
    const canvas = image.parentElement as HTMLElement;

    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 150, clientY: 130 });
    fireEvent.mouseUp(canvas, { clientX: 150, clientY: 130 });
    fireEvent.change(await screen.findByLabelText("Текст лексеми"), {
      target: { value: "нове" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти лексему" }));

    const confirmButton = await screen.findByRole("button", {
      name: "Зберегти попри збіг",
    });
    fireEvent.click(confirmButton);

    await vi.waitFor(() => {
      const confirmCall = fetchMock.mock.calls[1];
      if (!confirmCall) throw new Error("expected a second fetch call");
      const body = JSON.parse((confirmCall[1] as RequestInit).body as string);
      expect(body.confirm_duplicate).toBe(true);
    });
  });

  it("discards a drag smaller than the minimum selection size", async () => {
    stubContainerRect();

    renderCanvas();
    const image = await loadImage();
    const canvas = image.parentElement as HTMLElement;

    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 52, clientY: 51 });
    fireEvent.mouseUp(canvas, { clientX: 52, clientY: 51 });

    expect(screen.queryByLabelText("Текст лексеми")).not.toBeInTheDocument();
  });

  it("redrawing a selected lexeme submits the new box, keeping its text (BH-56)", async () => {
    stubContainerRect();
    const existing = lexemeFixture({ id: "lex-1", source_text: "старе" });
    const onSubmitUpdate = vi.fn().mockResolvedValue(lexemeFixture({ id: "lex-1" }));
    const onLexemeRedrawn = vi.fn();

    renderCanvas({
      lexemes: [existing],
      redrawingLexemeId: "lex-1",
      onSubmitUpdate,
      onLexemeRedrawn,
    });
    const image = await loadImage();
    const canvas = image.parentElement as HTMLElement;

    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 150, clientY: 130 });
    fireEvent.mouseUp(canvas, { clientX: 150, clientY: 130 });

    // No create form should appear -- redraw skips straight to submitting.
    expect(screen.queryByLabelText("Текст лексеми")).not.toBeInTheDocument();
    await vi.waitFor(() => {
      expect(onSubmitUpdate).toHaveBeenCalledWith("lex-1", {
        source_text: "старе",
        x: 100,
        y: 100,
        width: 200,
        height: 160,
        x2: null,
        y2: null,
        width2: null,
        height2: null,
      });
    });
    await vi.waitFor(() => {
      expect(onLexemeRedrawn).toHaveBeenCalledWith(
        expect.objectContaining({ id: "lex-1" }),
      );
    });
  });

  it("shows a redraw hint with a cancel button while redrawing", async () => {
    stubContainerRect();
    const onCancelRedraw = vi.fn();

    renderCanvas({
      lexemes: [lexemeFixture()],
      redrawingLexemeId: "lex-1",
      onCancelRedraw,
    });
    await loadImage();

    fireEvent.click(
      screen.getByRole("button", { name: "Скасувати перемальовування" }),
    );

    expect(onCancelRedraw).toHaveBeenCalled();
  });

  it("clicking a saved lexeme's box selects it", async () => {
    stubContainerRect();
    const onSelectLexeme = vi.fn();

    renderCanvas({ lexemes: [lexemeFixture({ id: "lex-7" })], onSelectLexeme });
    await loadImage();

    fireEvent.click(await screen.findByTitle("слово"));

    expect(onSelectLexeme).toHaveBeenCalledWith("lex-7");
  });

  it("hides other lexemes' boxes once one is selected", async () => {
    stubContainerRect();

    renderCanvas({
      lexemes: [
        lexemeFixture({ id: "lex-1", source_text: "перше" }),
        lexemeFixture({ id: "lex-2", source_text: "друге", x: 400 }),
      ],
      selectedLexemeId: "lex-1",
    });
    await loadImage();

    expect(await screen.findByTitle("перше")).toBeInTheDocument();
    expect(screen.queryByTitle("друге")).not.toBeInTheDocument();
  });

  it("scrolls to and focuses the selected lexeme's box (BH-70)", async () => {
    stubContainerRect();
    const scrollIntoViewMock = vi.fn();
    vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(
      scrollIntoViewMock,
    );

    renderCanvas({ lexemes: [lexemeFixture()], selectedLexemeId: "lex-1" });
    await loadImage();

    const box = await screen.findByTitle("слово");
    expect(scrollIntoViewMock).toHaveBeenCalledWith(
      expect.objectContaining({ block: "center" }),
    );
    expect(box).toHaveFocus();
  });

  it("dragging a resize handle resizes the selected lexeme's box", async () => {
    stubContainerRect();
    const existing = lexemeFixture({
      id: "lex-1",
      source_text: "слово",
      x: 100,
      y: 100,
      width: 200,
      height: 80,
    });
    const onSubmitUpdate = vi.fn().mockResolvedValue(lexemeFixture({ id: "lex-1" }));
    const onLexemeRedrawn = vi.fn();

    const { container } = renderCanvas({
      lexemes: [existing],
      selectedLexemeId: "lex-1",
      onSubmitUpdate,
      onLexemeRedrawn,
    });
    const image = await loadImage();
    const canvas = image.parentElement as HTMLElement;

    // Container is 500x700 displayed, natural size 1000x1400 -> scale 0.5x,
    // so box1's displayed rect is (50,50,100,40) and its se corner is (150,90).
    const handle = container.querySelector('[data-handle="se"]');
    expect(handle).not.toBeNull();
    fireEvent.mouseDown(handle as Element, { clientX: 150, clientY: 90 });
    fireEvent.mouseMove(canvas, { clientX: 170, clientY: 100 });
    fireEvent.mouseUp(canvas, { clientX: 170, clientY: 100 });

    await vi.waitFor(() => {
      expect(onSubmitUpdate).toHaveBeenCalledWith("lex-1", {
        source_text: "слово",
        x: 100,
        y: 100,
        width: 240,
        height: 100,
        x2: null,
        y2: null,
        width2: null,
        height2: null,
      });
    });
    await vi.waitFor(() => {
      expect(onLexemeRedrawn).toHaveBeenCalledWith(
        expect.objectContaining({ id: "lex-1" }),
      );
    });
  });

  it("renders a lexeme's second box when present", async () => {
    stubContainerRect();
    const withSecondBox = lexemeFixture({
      id: "lex-1",
      source_text: "слово",
      x2: 600,
      y2: 200,
      width2: 100,
      height2: 50,
    });

    renderCanvas({ lexemes: [withSecondBox] });
    await loadImage();

    expect(await screen.findAllByTitle("слово")).toHaveLength(2);
  });

  it("drawing a second box preserves box1 and reports it separately", async () => {
    stubContainerRect();
    const existing = lexemeFixture({
      id: "lex-1",
      source_text: "слово",
      x: 100,
      y: 100,
      width: 200,
      height: 80,
    });
    const onSubmitUpdate = vi.fn().mockResolvedValue(lexemeFixture({ id: "lex-1" }));
    const onSecondBoxDrawn = vi.fn();

    renderCanvas({
      lexemes: [existing],
      selectedLexemeId: "lex-1",
      secondBoxDraftLexemeId: "lex-1",
      onSubmitUpdate,
      onSecondBoxDrawn,
    });
    const image = await loadImage();
    const canvas = image.parentElement as HTMLElement;

    fireEvent.mouseDown(canvas, { clientX: 300, clientY: 100 });
    fireEvent.mouseMove(canvas, { clientX: 350, clientY: 130 });
    fireEvent.mouseUp(canvas, { clientX: 350, clientY: 130 });

    await vi.waitFor(() => {
      expect(onSubmitUpdate).toHaveBeenCalledWith("lex-1", {
        source_text: "слово",
        x: 100,
        y: 100,
        width: 200,
        height: 80,
        x2: 600,
        y2: 200,
        width2: 100,
        height2: 60,
      });
    });
    await vi.waitFor(() => {
      expect(onSecondBoxDrawn).toHaveBeenCalledWith(
        expect.objectContaining({ id: "lex-1" }),
      );
    });
  });

  it("shows a hint with a cancel button while drafting a second box", async () => {
    stubContainerRect();
    const onCancelSecondBoxDraft = vi.fn();

    renderCanvas({
      lexemes: [lexemeFixture()],
      secondBoxDraftLexemeId: "lex-1",
      onCancelSecondBoxDraft,
    });
    await loadImage();

    fireEvent.click(screen.getByRole("button", { name: "Скасувати" }));

    expect(onCancelSecondBoxDraft).toHaveBeenCalled();
  });

  it("renders an OCR suggestion overlay at its scaled position", async () => {
    stubContainerRect();

    renderCanvas({ suggestions: [suggestionFixture({ source_text: "слово" })] });
    await loadImage();

    const box = await screen.findByTitle("слово");
    expect(box.className).toContain("border-lexeme-suggestion");
    // Container is 500x700 displayed, image natural size is 1000x1400 -> scale 0.5x.
    expect(box.style.left).toBe("50px");
    expect(box.style.top).toBe("50px");
    expect(box.style.width).toBe("100px");
    expect(box.style.height).toBe("40px");
  });

  it("clicking a suggestion pre-fills the text field and opens the confirm form", async () => {
    stubContainerRect();

    renderCanvas({ suggestions: [suggestionFixture({ source_text: "слово" })] });
    await loadImage();

    fireEvent.click(await screen.findByTitle("слово"));

    expect(await screen.findByLabelText("Текст лексеми")).toHaveValue("слово");
  });

  it("accepting a suggestion submits with origin ocr and notifies the caller", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(
      jsonResponse(
        201,
        lexemeFixture({ id: "lex-ocr", source_text: "слово", origin: "ocr" }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    stubContainerRect();
    const onAcceptSuggestion = vi.fn();
    const suggestion = suggestionFixture({ source_text: "слово" });

    renderCanvas({ suggestions: [suggestion], onAcceptSuggestion });
    await loadImage();

    fireEvent.click(await screen.findByTitle("слово"));
    fireEvent.click(screen.getByRole("button", { name: "Зберегти лексему" }));

    const createCall = await vi.waitFor(() => {
      const call = fetchMock.mock.calls[0];
      if (!call) throw new Error("expected a fetch call");
      return call;
    });
    const body = JSON.parse((createCall[1] as RequestInit).body as string);
    expect(body.origin).toBe("ocr");
    await vi.waitFor(() => {
      expect(onAcceptSuggestion).toHaveBeenCalledWith(suggestion);
    });
  });
});
