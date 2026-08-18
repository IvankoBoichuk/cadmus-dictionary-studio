import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DictionaryPageViewer } from "./DictionaryPageViewer";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("DictionaryPageViewer", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
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
});
