import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ScanProgressBar } from "./ScanProgressBar";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ScanProgressBar", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the processed/total count (AC2)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          total_pages: 3,
          processed_pages: 2,
          pages: [
            { page_number: 1, has_lexemes: true },
            { page_number: 2, has_lexemes: false },
            { page_number: 3, has_lexemes: true },
          ],
        }),
      ),
    );

    render(
      <ScanProgressBar
        dictionaryId="dict-1"
        currentPage={1}
        refreshToken={0}
        onNavigate={vi.fn()}
      />,
    );

    expect(
      await screen.findByText("Опрацьовано 2 / 3 сторінок"),
    ).toBeInTheDocument();
  });

  it("visually marks processed pages (AC3)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          total_pages: 2,
          processed_pages: 1,
          pages: [
            { page_number: 1, has_lexemes: true },
            { page_number: 2, has_lexemes: false },
          ],
        }),
      ),
    );

    render(
      <ScanProgressBar
        dictionaryId="dict-1"
        currentPage={1}
        refreshToken={0}
        onNavigate={vi.fn()}
      />,
    );

    const processed = await screen.findByRole("button", { name: "1" });
    const unprocessed = screen.getByRole("button", { name: "2" });
    expect(processed).toHaveAttribute("title", "Сторінка 1 — опрацьована");
    expect(unprocessed).toHaveAttribute("title", "Сторінка 2");
  });

  it("jumps to the next unprocessed page after the current one (AC4)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          total_pages: 4,
          processed_pages: 2,
          pages: [
            { page_number: 1, has_lexemes: true },
            { page_number: 2, has_lexemes: false },
            { page_number: 3, has_lexemes: true },
            { page_number: 4, has_lexemes: false },
          ],
        }),
      ),
    );
    const onNavigate = vi.fn();

    render(
      <ScanProgressBar
        dictionaryId="dict-1"
        currentPage={3}
        refreshToken={0}
        onNavigate={onNavigate}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Перейти до неопрацьованої сторінки" }),
    );

    expect(onNavigate).toHaveBeenCalledWith(4);
  });

  it("wraps around to the first unprocessed page when none remain after current", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          total_pages: 3,
          processed_pages: 2,
          pages: [
            { page_number: 1, has_lexemes: false },
            { page_number: 2, has_lexemes: true },
            { page_number: 3, has_lexemes: true },
          ],
        }),
      ),
    );
    const onNavigate = vi.fn();

    render(
      <ScanProgressBar
        dictionaryId="dict-1"
        currentPage={3}
        refreshToken={0}
        onNavigate={onNavigate}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "Перейти до неопрацьованої сторінки" }),
    );

    expect(onNavigate).toHaveBeenCalledWith(1);
  });

  it("disables the jump button once every page is processed", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          total_pages: 1,
          processed_pages: 1,
          pages: [{ page_number: 1, has_lexemes: true }],
        }),
      ),
    );

    render(
      <ScanProgressBar
        dictionaryId="dict-1"
        currentPage={1}
        refreshToken={0}
        onNavigate={vi.fn()}
      />,
    );

    expect(
      await screen.findByRole("button", { name: "Усі сторінки опрацьовано" }),
    ).toBeDisabled();
  });

  it("navigates directly when a page marker is clicked", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          total_pages: 2,
          processed_pages: 0,
          pages: [
            { page_number: 1, has_lexemes: false },
            { page_number: 2, has_lexemes: false },
          ],
        }),
      ),
    );
    const onNavigate = vi.fn();

    render(
      <ScanProgressBar
        dictionaryId="dict-1"
        currentPage={1}
        refreshToken={0}
        onNavigate={onNavigate}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "2" }));

    expect(onNavigate).toHaveBeenCalledWith(2);
  });

  it("enqueues the OCR scan queue and shows its progress", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, {
          total_pages: 2,
          processed_pages: 0,
          pages: [
            { page_number: 1, has_lexemes: false },
            { page_number: 2, has_lexemes: false },
          ],
        }),
      )
      .mockResolvedValueOnce(jsonResponse(202, { task_id: "scan-1", status: "queued" }));
    vi.stubGlobal("fetch", fetchMock);

    render(
      <ScanProgressBar
        dictionaryId="dict-1"
        currentPage={1}
        refreshToken={0}
        onNavigate={vi.fn()}
      />,
    );

    // Wait for the loaded progress grid (not just the trigger button, which
    // is also present in the transient loading state) so we click the button
    // instance that actually stays mounted, rather than one about to be
    // replaced when the Fragment/div root swaps on load.
    await screen.findByText("Опрацьовано 0 / 2 сторінок");
    const trigger = screen.getByRole("button", {
      name: "Запустити чергу OCR для всього словника",
    });
    await act(async () => {
      fireEvent.click(trigger);
    });

    expect(screen.getByRole("button", { name: "Опрацьовуємо чергу…" })).toBeDisabled();
  });
});
