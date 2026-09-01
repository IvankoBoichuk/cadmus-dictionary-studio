import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ReviewQueueItemResponse } from "../api";
import { ReviewQueuePage } from "./ReviewQueuePage";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function item(
  overrides: Partial<ReviewQueueItemResponse> = {},
): ReviewQueueItemResponse {
  return {
    entry_id: "11111111-1111-1111-1111-111111111111",
    dictionary_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    dictionary_title: "Тестовий словник",
    headword: "слово",
    status: "ready_to_review",
    field_count: 3,
    updated_at: "2026-08-20T12:00:00Z",
    ...overrides,
  };
}

/**
 * Answers `GET /review/queue` from `queuePages` in call order (last page
 * repeats), and every `POST /review/entries/*` from `actions` in call order.
 */
function stubFetch(
  queuePages: ReviewQueueItemResponse[][],
  actions: Array<() => Response> = [],
) {
  const pages = [...queuePages];
  const queued = [...actions];
  const mock = vi.fn((input: unknown, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (method === "GET" && url.endsWith("/review/queue")) {
      const page = pages.length > 1 ? pages.shift()! : pages[0];
      return Promise.resolve(jsonResponse(200, page ?? []));
    }
    const next = queued.shift();
    return Promise.resolve(
      next ? next() : jsonResponse(200, { entry_id: "x", status: "complete" }),
    );
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/review"]}>
      <ReviewQueuePage />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ReviewQueuePage", () => {
  it("lists queued entries grouped by dictionary", async () => {
    stubFetch([
      [
        item({ headword: "альфа", entry_id: "1" }),
        item({
          headword: "бета",
          entry_id: "2",
          dictionary_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
          dictionary_title: "Другий словник",
        }),
      ],
    ]);
    renderPage();

    expect(
      await screen.findByRole("link", { name: "альфа" }),
    ).toHaveAttribute("href", "/entries/1");
    expect(screen.getByText("Тестовий словник")).toBeInTheDocument();
    expect(screen.getByText("Другий словник")).toBeInTheDocument();
  });

  it("shows an empty state when nothing is awaiting review", async () => {
    stubFetch([[]]);
    renderPage();

    expect(
      await screen.findByText("Немає статей, що очікують перевірки."),
    ).toBeInTheDocument();
  });

  it("approves an entry and refreshes the queue", async () => {
    const mock = stubFetch(
      [[item({ headword: "альфа", entry_id: "1" })], []],
      [() => jsonResponse(200, { entry_id: "1", status: "complete" })],
    );
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Схвалити" }));

    await waitFor(() =>
      expect(
        screen.getByText("Немає статей, що очікують перевірки."),
      ).toBeInTheDocument(),
    );
    const approveCall = mock.mock.calls.find(
      ([u, i]) =>
        String(u).endsWith("/review/entries/1/approve") &&
        (i as RequestInit | undefined)?.method === "POST",
    );
    expect(approveCall).toBeDefined();
  });

  it("sends an entry back with a note", async () => {
    const mock = stubFetch(
      [[item({ headword: "альфа", entry_id: "1" })], []],
      [() => jsonResponse(200, { entry_id: "1", status: "draft" })],
    );
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Повернути" }));
    fireEvent.change(
      await screen.findByPlaceholderText("Що потрібно доопрацювати?"),
      { target: { value: "виправте приклади" } },
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Повернути на доопрацювання" }),
    );

    await waitFor(() => {
      const call = mock.mock.calls.find(
        ([u, i]) =>
          String(u).endsWith("/review/entries/1/send-back") &&
          (i as RequestInit | undefined)?.method === "POST",
      );
      expect(call).toBeDefined();
      expect(JSON.parse((call![1] as RequestInit).body as string)).toEqual({
        note: "виправте приклади",
      });
    });
  });
});
