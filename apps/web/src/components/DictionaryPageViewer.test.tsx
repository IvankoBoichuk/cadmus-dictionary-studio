import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DictionaryPageViewer } from "./DictionaryPageViewer";

function RouterWrapper({ children }: { children: ReactNode }) {
  return <MemoryRouter>{children}</MemoryRouter>;
}

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
    if (url.includes("/scan-progress")) {
      return Promise.resolve(
        jsonResponse(200, { total_pages: totalPages, processed_pages: 0, pages: [] }),
      );
    }
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
    vi.stubGlobal("fetch", endpointAwareFetch(12, []));

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={3} onNavigate={vi.fn()} />,
      { wrapper: RouterWrapper },
    );

    const image = await screen.findByAltText("Сторінка 3 з 12");
    expect(image).toHaveAttribute("src", "/api/dictionaries/dict-1/pages/3");
    expect(screen.getByText("Сторінка 3 / 12")).toBeInTheDocument();
  });

  it("calls onNavigate with the next and previous page numbers", async () => {
    vi.stubGlobal("fetch", endpointAwareFetch(12, []));
    const onNavigate = vi.fn();

    render(
      <DictionaryPageViewer
        dictionaryId="dict-1"
        pageNumber={3}
        onNavigate={onNavigate}
      />,
      { wrapper: RouterWrapper },
    );
    await screen.findByAltText("Сторінка 3 з 12");

    fireEvent.click(screen.getByRole("button", { name: "Наступна →" }));
    expect(onNavigate).toHaveBeenCalledWith(4);

    fireEvent.click(screen.getByRole("button", { name: "← Попередня" }));
    expect(onNavigate).toHaveBeenCalledWith(2);
  });

  it("disables the previous button on the first page and next on the last", async () => {
    vi.stubGlobal("fetch", endpointAwareFetch(2, []));

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={2} onNavigate={vi.fn()} />,
      { wrapper: RouterWrapper },
    );
    await screen.findByAltText("Сторінка 2 з 2");

    expect(screen.getByRole("button", { name: "Наступна →" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "← Попередня" })).toBeEnabled();
  });

  it("explains when the dictionary has no configured page ranges yet", async () => {
    vi.stubGlobal("fetch", endpointAwareFetch(0, []));

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={1} onNavigate={vi.fn()} />,
      { wrapper: RouterWrapper },
    );

    expect(
      await screen.findByText(/ще не вказано жодного діапазону сторінок/),
    ).toBeInTheDocument();
  });

  it("clamps an out-of-range requested page back onto the viewer", async () => {
    vi.stubGlobal("fetch", endpointAwareFetch(5, []));
    const onNavigate = vi.fn();

    render(
      <DictionaryPageViewer
        dictionaryId="dict-1"
        pageNumber={99}
        onNavigate={onNavigate}
      />,
      { wrapper: RouterWrapper },
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
      { wrapper: RouterWrapper },
    );
    loadPageImage(await screen.findByAltText("Сторінка 1 з 1"));

    const listItem = await screen.findByRole("button", { name: /слово/ });
    expect(listItem).toHaveTextContent("Сторінка 1");

    fireEvent.click(listItem);

    expect(listItem).toHaveAttribute("aria-pressed", "true");
    expect((await screen.findByTitle("слово")).className).toContain(
      "border-selected",
    );
  });

  it("shows an empty-state message when the page has no lexemes yet", async () => {
    vi.stubGlobal("fetch", endpointAwareFetch(1, []));

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={1} onNavigate={vi.fn()} />,
      { wrapper: RouterWrapper },
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
      if (url.includes("/scan-progress")) {
        return Promise.resolve(
          jsonResponse(200, { total_pages: 1, processed_pages: 0, pages: [] }),
        );
      }
      return Promise.resolve(jsonResponse(200, { total_pages: 1 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={1} onNavigate={vi.fn()} />,
      { wrapper: RouterWrapper },
    );
    const image = loadPageImage(await screen.findByAltText("Сторінка 1 з 1"));
    const canvas = image.parentElement as HTMLElement;

    expect(await screen.findByText(/ще немає виділених лексем/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Виділити текст" }));
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

  it("saving edited text preserves an existing second box (regression)", async () => {
    stubContainerRect();
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/lexemes/lex-1") && init?.method === "PATCH") {
        const body = JSON.parse(init.body as string) as Record<string, unknown>;
        return Promise.resolve(
          jsonResponse(200, {
            id: "lex-1",
            dictionary_id: "dict-1",
            page_id: "page-1",
            origin: "manual",
            created_at: "2026-08-18T00:00:00Z",
            created_by: "user-1",
            updated_at: "2026-08-18T00:00:00Z",
            updated_by: "user-1",
            ...body,
          }),
        );
      }
      if (url.includes("/lexemes")) {
        return Promise.resolve(
          jsonResponse(200, [
            {
              id: "lex-1",
              dictionary_id: "dict-1",
              page_id: "page-1",
              source_text: "старе",
              x: 10,
              y: 10,
              width: 100,
              height: 40,
              x2: 600,
              y2: 10,
              width2: 90,
              height2: 40,
              origin: "manual",
              created_at: "2026-08-18T00:00:00Z",
              created_by: "user-1",
              updated_at: "2026-08-18T00:00:00Z",
              updated_by: "user-1",
            },
          ]),
        );
      }
      if (url.includes("/scan-progress")) {
        return Promise.resolve(
          jsonResponse(200, { total_pages: 1, processed_pages: 0, pages: [] }),
        );
      }
      return Promise.resolve(jsonResponse(200, { total_pages: 1 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={1} onNavigate={vi.fn()} />,
      { wrapper: RouterWrapper },
    );
    loadPageImage(await screen.findByAltText("Сторінка 1 з 1"));

    fireEvent.click(await screen.findByRole("button", { name: "Редагувати текст" }));
    fireEvent.change(screen.getByLabelText("Текст лексеми"), {
      target: { value: "нове" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    await vi.waitFor(() => {
      const patchCall = fetchMock.mock.calls.find(
        (call) =>
          String(call[0]).includes("/lexemes/lex-1") &&
          (call[1] as RequestInit | undefined)?.method === "PATCH",
      );
      expect(patchCall).toBeDefined();
      const body = JSON.parse((patchCall?.[1] as RequestInit).body as string);
      expect(body).toEqual({
        source_text: "нове",
        x: 10,
        y: 10,
        width: 100,
        height: 40,
        x2: 600,
        y2: 10,
        width2: 90,
        height2: 40,
      });
    });
  });

  it("enqueues the whole-dictionary OCR scan queue from the top bar", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/ocr-scan") && init?.method === "POST") {
        return Promise.resolve(
          jsonResponse(202, { task_id: "scan-1", status: "queued" }),
        );
      }
      if (url.includes("/lexemes")) return Promise.resolve(jsonResponse(200, []));
      if (url.includes("/scan-progress")) {
        return Promise.resolve(
          jsonResponse(200, { total_pages: 2, processed_pages: 0, pages: [] }),
        );
      }
      return Promise.resolve(jsonResponse(200, { total_pages: 2 }));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <DictionaryPageViewer dictionaryId="dict-1" pageNumber={1} onNavigate={vi.fn()} />,
      { wrapper: RouterWrapper },
    );
    await screen.findByAltText("Сторінка 1 з 2");

    fireEvent.click(
      screen.getByRole("button", {
        name: "Запустити чергу OCR для всього словника",
      }),
    );

    await vi.waitFor(() =>
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/ocr-scan") &&
            (call[1] as RequestInit | undefined)?.method === "POST",
        ),
      ).toBe(true),
    );
    expect(
      await screen.findByRole("button", { name: "Опрацьовуємо чергу…" }),
    ).toBeDisabled();
  });
});
