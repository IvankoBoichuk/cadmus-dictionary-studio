import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProcessingTaskResponse } from "../api";
import { DictionaryTasksPage } from "./DictionaryTasksPage";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function task(
  overrides: Partial<ProcessingTaskResponse> = {},
): ProcessingTaskResponse {
  return {
    id: crypto.randomUUID(),
    dictionary_id: DICTIONARY_ID,
    kind: "dictionary_scan",
    status: "succeeded",
    target_id: null,
    target_label: null,
    error: null,
    result: null,
    retry_of_id: null,
    created_at: "2026-09-01T10:00:00Z",
    started_at: "2026-09-01T10:00:00Z",
    finished_at: "2026-09-01T10:01:00Z",
    updated_at: "2026-09-01T10:01:00Z",
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[`/dictionaries/${DICTIONARY_ID}/tasks`]}>
      <Routes>
        <Route
          path="/dictionaries/:dictionaryId/tasks"
          element={<DictionaryTasksPage />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("DictionaryTasksPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("lists tasks with their kind, target and status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, [
          task({
            kind: "entry_extraction",
            target_label: "хата",
            status: "running",
          }),
          task({ kind: "article_schema_generation", status: "succeeded" }),
        ]),
      ),
    );

    renderPage();

    expect(
      await screen.findByText("Розбір структури статті"),
    ).toBeInTheDocument();
    expect(screen.getByText("хата")).toBeInTheDocument();
    // "Виконується" also labels the status filter chip, so there are two.
    expect(screen.getAllByText("Виконується").length).toBeGreaterThan(1);
    expect(screen.getByText("Генерація схеми статті")).toBeInTheDocument();
  });

  it("shows an empty state when there are no tasks", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, [])));

    renderPage();

    expect(
      await screen.findByText("Фонових задач для цього словника ще не було."),
    ).toBeInTheDocument();
  });

  it("filters the list by status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, [
          task({ kind: "dictionary_scan", status: "succeeded" }),
          task({
            kind: "entry_extraction",
            status: "failed",
            error: "boom",
            target_label: "слово",
          }),
        ]),
      ),
    );

    renderPage();
    await screen.findByText("OCR-скан словника");

    fireEvent.click(screen.getByRole("button", { name: /Помилка/ }));

    expect(screen.queryByText("OCR-скан словника")).not.toBeInTheDocument();
    expect(screen.getByText("Розбір структури статті")).toBeInTheDocument();
  });

  it("retries a failed task and surfaces a 409 message", async () => {
    const failed = task({
      kind: "dictionary_scan",
      status: "failed",
      error: "OCR upstream error",
    });
    const fetchMock = vi.fn((_input: unknown, init?: RequestInit) => {
      if (init?.method === "POST") {
        return Promise.resolve(
          jsonResponse(409, {
            code: "not_retryable",
            message: "Перезапустити можна лише невдалу задачу.",
          }),
        );
      }
      return Promise.resolve(jsonResponse(200, [failed]));
    });
    vi.stubGlobal("fetch", fetchMock);

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Перезапустити" }));

    expect(
      await screen.findByText("Перезапустити можна лише невдалу задачу."),
    ).toBeInTheDocument();
    const postCall = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit | undefined)?.method === "POST",
    );
    expect(String(postCall![0])).toContain(`/tasks/${failed.id}/retry`);
  });

  it("reveals the error detail on demand", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, [
          task({ status: "failed", error: "Traceback: KaboomError" }),
        ]),
      ),
    );

    renderPage();

    const summary = await screen.findByText("Деталі помилки");
    fireEvent.click(summary);
    await waitFor(() =>
      expect(screen.getByText("Traceback: KaboomError")).toBeVisible(),
    );
  });
});
