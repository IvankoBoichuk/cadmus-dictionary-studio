import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PageRangesResponse } from "../api";
import { PageRangeEditor } from "./PageRangeEditor";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function initialResponse(
  overrides: Partial<PageRangesResponse> = {},
): PageRangesResponse {
  return {
    page_count: 300,
    ranges: [],
    merged: false,
    ...overrides,
  };
}

describe("PageRangeEditor", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the PDF's page count and any already-saved ranges", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          200,
          initialResponse({ ranges: [{ start_page: 10, end_page: 220 }] }),
        ),
      ),
    );

    render(<PageRangeEditor dictionaryId="dict-1" />);

    expect(await screen.findByText(/300 стор\./)).toBeInTheDocument();
    expect(screen.getByLabelText("Початкова сторінка")).toHaveValue("10");
    expect(screen.getByLabelText("Кінцева сторінка")).toHaveValue("220");
  });

  it("explains that ranges are unavailable before the PDF is verified", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, initialResponse({ page_count: null }))),
    );

    render(<PageRangeEditor dictionaryId="dict-1" />);

    expect(
      await screen.findByText(/PDF ще не пройшов перевірку структури/),
    ).toBeInTheDocument();
  });

  it("adds, edits, and removes range rows", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, initialResponse())),
    );

    render(<PageRangeEditor dictionaryId="dict-1" />);
    await screen.findByText(/300 стор\./);

    fireEvent.click(screen.getByRole("button", { name: "Додати діапазон" }));
    fireEvent.change(screen.getByLabelText("Початкова сторінка"), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText("Кінцева сторінка"), {
      target: { value: "50" },
    });

    expect(screen.getByLabelText("Початкова сторінка")).toHaveValue("5");

    fireEvent.click(screen.getByRole("button", { name: "Видалити діапазон 1" }));
    expect(screen.queryByLabelText("Початкова сторінка")).not.toBeInTheDocument();
  });

  it("shows a client-side error for a page outside the PDF's bounds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(200, initialResponse({ page_count: 100 }))),
    );

    render(<PageRangeEditor dictionaryId="dict-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Додати діапазон" }));
    fireEvent.change(screen.getByLabelText("Початкова сторінка"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Кінцева сторінка"), {
      target: { value: "999" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти діапазони" }));

    expect(
      await screen.findByText(/Кінцева сторінка має бути в межах від 1 до 100/),
    ).toBeInTheDocument();
  });

  it("saves valid ranges and reports when the server merged an overlap", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, initialResponse({ page_count: 100 })))
      .mockResolvedValueOnce(
        jsonResponse(
          200,
          initialResponse({
            page_count: 100,
            ranges: [{ start_page: 1, end_page: 40 }],
            merged: true,
          }),
        ),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<PageRangeEditor dictionaryId="dict-1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Додати діапазон" }));
    fireEvent.change(screen.getByLabelText("Початкова сторінка"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Кінцева сторінка"), {
      target: { value: "20" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти діапазони" }));

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("перетиналися й були"),
    );
    expect(screen.getByLabelText("Кінцева сторінка")).toHaveValue("40");
  });
});
