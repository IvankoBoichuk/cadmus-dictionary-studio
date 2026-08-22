import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useOcrSuggestions } from "./useOcrSuggestions";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";
const PAGE_NUMBER = 3;

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("useOcrSuggestions", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("starts idle", () => {
    const { result } = renderHook(() => useOcrSuggestions(DICTIONARY_ID, PAGE_NUMBER));
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("enqueues, polls, and stops once the task succeeds", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(202, { task_id: "task-1", status: "queued" }))
      .mockResolvedValueOnce(
        jsonResponse(200, { task_id: "task-1", status: "running" }),
      )
      .mockResolvedValueOnce(
        jsonResponse(200, {
          task_id: "task-1",
          status: "succeeded",
          suggestions: [
            { source_text: "слово", x: 1, y: 2, width: 10, height: 5, confidence: 0.9 },
          ],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useOcrSuggestions(DICTIONARY_ID, PAGE_NUMBER));

    await act(async () => {
      await result.current.trigger();
    });
    expect(result.current.state).toEqual({ status: "queued", taskId: "task-1" });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(result.current.state).toEqual({ status: "running", taskId: "task-1" });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(result.current.state).toEqual({
      status: "succeeded",
      taskId: "task-1",
      suggestions: [
        { source_text: "слово", x: 1, y: 2, width: 10, height: 5, confidence: 0.9 },
      ],
    });

    const callsAfterSucceeding = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(fetchMock.mock.calls.length).toBe(callsAfterSucceeding);
  });

  it("stops polling once the task fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(202, { task_id: "task-1", status: "queued" }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          task_id: "task-1",
          status: "failed",
          error: "tesseract failed",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useOcrSuggestions(DICTIONARY_ID, PAGE_NUMBER));

    await act(async () => {
      await result.current.trigger();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(result.current.state).toEqual({
      status: "failed",
      message: "tesseract failed",
    });

    const callsAfterFailing = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(fetchMock.mock.calls.length).toBe(callsAfterFailing);
  });

  it("surfaces an error and does not start polling when enqueue fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(404, { code: "not_found", message: "Сторінку не знайдено." }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useOcrSuggestions(DICTIONARY_ID, PAGE_NUMBER));

    await act(async () => {
      await result.current.trigger();
    });

    expect(result.current.state).toEqual({
      status: "failed",
      message: "Сторінку не знайдено.",
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(fetchMock.mock.calls.length).toBe(1);
  });

  it("dismissSuggestion removes one suggestion from the succeeded state", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(202, { task_id: "task-1", status: "queued" }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          task_id: "task-1",
          status: "succeeded",
          suggestions: [
            { source_text: "перше", x: 1, y: 1, width: 5, height: 5, confidence: 0.9 },
            { source_text: "друге", x: 9, y: 9, width: 5, height: 5, confidence: 0.8 },
          ],
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useOcrSuggestions(DICTIONARY_ID, PAGE_NUMBER));

    await act(async () => {
      await result.current.trigger();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(result.current.state.status).toBe("succeeded");
    const suggestionToRemove =
      result.current.state.status === "succeeded"
        ? result.current.state.suggestions[0]
        : undefined;
    expect(suggestionToRemove).toBeDefined();

    act(() => {
      if (suggestionToRemove) result.current.dismissSuggestion(suggestionToRemove);
    });

    expect(result.current.state.status === "succeeded" && result.current.state.suggestions).toEqual(
      [{ source_text: "друге", x: 9, y: 9, width: 5, height: 5, confidence: 0.8 }],
    );
  });

  it("reset returns to idle and stops polling", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(202, { task_id: "task-1", status: "queued" }))
      .mockResolvedValue(jsonResponse(200, { task_id: "task-1", status: "running" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useOcrSuggestions(DICTIONARY_ID, PAGE_NUMBER));

    await act(async () => {
      await result.current.trigger();
    });

    act(() => {
      result.current.reset();
    });
    expect(result.current.state).toEqual({ status: "idle" });

    const callsAfterReset = fetchMock.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(fetchMock.mock.calls.length).toBe(callsAfterReset);
  });
});
