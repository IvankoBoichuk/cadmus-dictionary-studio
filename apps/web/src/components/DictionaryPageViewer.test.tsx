import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DictionaryPageViewer } from "./DictionaryPageViewer";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function endpointAwareFetch(totalPages: number, lexemes: unknown[]) {
  return vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/lexemes")) return Promise.resolve(jsonResponse(200, lexemes));
    return Promise.resolve(jsonResponse(200, { total_pages: totalPages }));
  });
}

/** Simulates the image finishing its natural-size load, as the real browser would. */
function loadPageImage(image: HTMLElement): HTMLElement {
  Object.defineProperty(image, "naturalWidth", { value: 1000, configurable: true });
  Object.defineProperty(image, "naturalHeight", { value: 1400, configurable: true });
  fireEvent.load(image);
  return image;
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

describe("DictionaryPageViewer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows the requested page and the total page count", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { total_pages: 12 })),
    );

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={3} onNavigate={vi.fn()} />,
    );

    const image = await screen.findByAltText("Сторінка 3 з 12");
    expect(image).toHaveAttribute("src", "/api/dictionaries/dict-1/pages/3");
    expect(screen.getByRole("status")).toHaveTextContent("Сторінка 3 / 12");
  });

  it("calls onNavigate with the next and previous page numbers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { total_pages: 12 })),
    );
    const onNavigate = vi.fn();

    render(
      <DictionaryPageViewer
        dictionaryId="dict-1"
        pageNumber={3}
        onNavigate={onNavigate}
      />,
    );
    await screen.findByAltText("Сторінка 3 з 12");

    fireEvent.click(screen.getByRole("button", { name: "Наступна →" }));
    expect(onNavigate).toHaveBeenCalledWith(4);

    fireEvent.click(screen.getByRole("button", { name: "← Попередня" }));
    expect(onNavigate).toHaveBeenCalledWith(2);
  });

  it("disables the previous button on the first page and next on the last", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { total_pages: 2 })),
    );

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={2} onNavigate={vi.fn()} />,
    );
    await screen.findByAltText("Сторінка 2 з 2");

    expect(screen.getByRole("button", { name: "Наступна →" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "← Попередня" })).toBeEnabled();
  });

  it("explains when the dictionary has no configured page ranges yet", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { total_pages: 0 })),
    );

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={1} onNavigate={vi.fn()} />,
    );

    expect(
      await screen.findByText(/ще не вказано жодного діапазону сторінок/),
    ).toBeInTheDocument();
  });

  it("clamps an out-of-range requested page back onto the viewer", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, { total_pages: 5 })),
    );
    const onNavigate = vi.fn();

    render(
      <DictionaryPageViewer
        dictionaryId="dict-1"
        pageNumber={99}
        onNavigate={onNavigate}
      />,
    );

    await screen.findByAltText("Сторінка 5 з 5");
    expect(onNavigate).toHaveBeenCalledWith(5);
  });

  it("lists the page's lexemes and highlights one on click (BH-55 AC1-AC3)", async () => {
    stubContainerRect();
    vi.stubGlobal(
      "fetch",
      endpointAwareFetch(1, [
        {
          id: "lex-1",
          dictionary_id: "dict-1",
          page_id: "page-1",
          source_text: "слово",
          x: 10,
          y: 10,
          width: 100,
          height: 40,
          origin: "manual",
          created_at: "2026-08-18T00:00:00Z",
          created_by: "user-1",
          updated_at: "2026-08-18T00:00:00Z",
          updated_by: "user-1",
        },
      ]),
    );

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={1} onNavigate={vi.fn()} />,
    );
    loadPageImage(await screen.findByAltText("Сторінка 1 з 1"));

    const listItem = await screen.findByRole("button", { name: /слово/ });
    expect(listItem).toHaveTextContent("Сторінка 1");

    fireEvent.click(listItem);

    expect(listItem).toHaveAttribute("aria-pressed", "true");
    expect((await screen.findByTitle("слово")).className).toContain(
      "lexeme-box--selected",
    );
  });

  it("shows an empty-state message when the page has no lexemes yet", async () => {
    vi.stubGlobal("fetch", endpointAwareFetch(1, []));

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={1} onNavigate={vi.fn()} />,
    );
    await screen.findByAltText("Сторінка 1 з 1");

    expect(
      await screen.findByText(/ще немає виділених лексем/),
    ).toBeInTheDocument();
  });

  it("adds a newly drawn lexeme to the list without a reload (AC4)", async () => {
    stubContainerRect();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/lexemes") && init?.method === "POST") {
        return Promise.resolve(
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
      }
      if (url.includes("/lexemes")) return Promise.resolve(jsonResponse(200, []));
      return Promise.resolve(jsonResponse(200, { total_pages: 1 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={1} onNavigate={vi.fn()} />,
    );
    const image = loadPageImage(await screen.findByAltText("Сторінка 1 з 1"));
    const canvas = image.parentElement as HTMLElement;

    expect(await screen.findByText(/ще немає виділених лексем/)).toBeInTheDocument();

    fireEvent.mouseDown(canvas, { clientX: 50, clientY: 50 });
    fireEvent.mouseMove(canvas, { clientX: 150, clientY: 130 });
    fireEvent.mouseUp(canvas, { clientX: 150, clientY: 130 });
    fireEvent.change(await screen.findByLabelText("Текст лексеми"), {
      target: { value: "нове" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти лексему" }));

    expect(await screen.findByRole("button", { name: /нове/ })).toBeInTheDocument();
    expect(
      screen.queryByText(/ще немає виділених лексем/),
    ).not.toBeInTheDocument();
  });
});
