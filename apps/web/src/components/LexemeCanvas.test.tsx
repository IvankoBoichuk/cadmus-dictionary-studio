import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LexemeResponse } from "../api";
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
    created_at: "2026-08-18T00:00:00Z",
    created_by: "user-1",
    updated_at: "2026-08-18T00:00:00Z",
    updated_by: "user-1",
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
      "lexeme-box--selected",
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
});
