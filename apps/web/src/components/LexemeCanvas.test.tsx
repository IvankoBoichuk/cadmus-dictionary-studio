import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

describe("LexemeCanvas", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("highlights the already-saved lexemes on the page (AC7)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, [
          {
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
          },
        ]),
      ),
    );
    stubContainerRect();

    render(
      <LexemeCanvas
        dictionaryId="dict-1"
        pageNumber={1}
        imageUrl="/api/dictionaries/dict-1/pages/1"
        imageAlt="Сторінка 1 з 1"
      />,
    );
    await loadImage();

    expect(await screen.findByTitle("слово")).toBeInTheDocument();
  });

  it("draws a box and opens the text form on mouse up (AC1, AC2, AC3)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [])));
    stubContainerRect();

    render(
      <LexemeCanvas
        dictionaryId="dict-1"
        pageNumber={1}
        imageUrl="/api/dictionaries/dict-1/pages/1"
        imageAlt="Сторінка 1 з 1"
      />,
    );
    const image = await loadImage();

    const canvas = image.parentElement as HTMLElement;
    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 150, clientY: 130 });
    fireEvent.mouseUp(canvas, { clientX: 150, clientY: 130 });

    expect(await screen.findByLabelText("Текст лексеми")).toBeInTheDocument();
  });

  it("submits the drawn box converted into natural page coordinates", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, []))
      .mockResolvedValueOnce(
        jsonResponse(201, {
          id: "lex-new",
          dictionary_id: "dict-1",
          page_id: "page-1",
          source_text: "нове",
          x: 100,
          y: 100,
          width: 200,
          height: 160,
          origin: "manual",
          created_at: "2026-08-18T00:00:00Z",
          created_by: "user-1",
          updated_at: "2026-08-18T00:00:00Z",
          updated_by: "user-1",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    stubContainerRect();

    render(
      <LexemeCanvas
        dictionaryId="dict-1"
        pageNumber={1}
        imageUrl="/api/dictionaries/dict-1/pages/1"
        imageAlt="Сторінка 1 з 1"
      />,
    );
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

    await screen.findByTitle("нове");
    const createCall = fetchMock.mock.calls[1];
    if (!createCall) throw new Error("expected a second fetch call");
    const body = JSON.parse((createCall[1] as RequestInit).body as string);
    expect(body).toEqual({
      source_text: "нове",
      x: 100,
      y: 100,
      width: 200,
      height: 160,
      confirm_duplicate: false,
    });
  });

  it("offers to confirm and resubmit when the server reports a duplicate", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, []))
      .mockResolvedValueOnce(
        jsonResponse(409, {
          code: "duplicate_lexeme",
          existing_lexeme_id: "lex-existing",
          message: "Схожа лексема вже виділена на цій сторінці.",
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(201, {
          id: "lex-confirmed",
          dictionary_id: "dict-1",
          page_id: "page-1",
          source_text: "нове",
          x: 100,
          y: 100,
          width: 200,
          height: 160,
          origin: "manual",
          created_at: "2026-08-18T00:00:00Z",
          created_by: "user-1",
          updated_at: "2026-08-18T00:00:00Z",
          updated_by: "user-1",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    stubContainerRect();

    render(
      <LexemeCanvas
        dictionaryId="dict-1"
        pageNumber={1}
        imageUrl="/api/dictionaries/dict-1/pages/1"
        imageAlt="Сторінка 1 з 1"
      />,
    );
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

    await screen.findByTitle("нове");
    const confirmCall = fetchMock.mock.calls[2];
    if (!confirmCall) throw new Error("expected a third fetch call");
    const body = JSON.parse((confirmCall[1] as RequestInit).body as string);
    expect(body.confirm_duplicate).toBe(true);
  });

  it("discards a drag smaller than the minimum selection size", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [])));
    stubContainerRect();

    render(
      <LexemeCanvas
        dictionaryId="dict-1"
        pageNumber={1}
        imageUrl="/api/dictionaries/dict-1/pages/1"
        imageAlt="Сторінка 1 з 1"
      />,
    );
    const image = await loadImage();
    const canvas = image.parentElement as HTMLElement;

    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 52, clientY: 51 });
    fireEvent.mouseUp(canvas, { clientX: 52, clientY: 51 });

    expect(screen.queryByLabelText("Текст лексеми")).not.toBeInTheDocument();
  });
});
