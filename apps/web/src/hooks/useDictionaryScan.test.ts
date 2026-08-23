import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDictionaryScan } from "./useDictionaryScan";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("useDictionaryScan", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("starts idle", () => {
    const { result } = renderHook(() => useDictionaryScan(DICTIONARY_ID));
    expect(result.current.state).toEqual({ status: "idle" });
  });

  it("enqueues, polls progress, and stops once the task succeeds", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(202, { task_id: "task-1", status: "queued" }))
      .mockResolvedValueOnce(
        jsonResponse(200, {
          task_id: "task-1",
          status: "running",
          processed_pages: 2,
          total_pages: 5,
          created_lexemes: 6,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse(200, {
          task_id: "task-1",
          status: "succeeded",
          processed_pages: 5,
          total_pages: 5,
          created_lexemes: 14,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDictionaryScan(DICTIONARY_ID));

    await act(async () => {
      await result.current.trigger();
    });
    expect(result.current.state).toEqual({
      status: "queued",
      taskId: "task-1",
      processedPages: 0,
      totalPages: 0,
      createdLexemes: 0,
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(result.current.state).toEqual({
      status: "running",
      taskId: "task-1",
      processedPages: 2,
      totalPages: 5,
      createdLexemes: 6,
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    expect(result.current.state).toEqual({
      status: "succeeded",
      taskId: "task-1",
      processedPages: 5,
      totalPages: 5,
      createdLexemes: 14,
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
          error: "dictionary scan task failed",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDictionaryScan(DICTIONARY_ID));

    await act(async () => {
      await result.current.trigger();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(result.current.state).toEqual({
      status: "failed",
      message: "dictionary scan task failed",
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
        jsonResponse(404, { code: "not_found", message: "Словник не знайдено." }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDictionaryScan(DICTIONARY_ID));

    await act(async () => {
      await result.current.trigger();
    });

    expect(result.current.state).toEqual({
      status: "failed",
      message: "Словник не знайдено.",
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(fetchMock.mock.calls.length).toBe(1);
  });

  it("reset returns to idle and stops polling", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(202, { task_id: "task-1", status: "queued" }))
      .mockResolvedValue(
        jsonResponse(200, {
          task_id: "task-1",
          status: "running",
          processed_pages: 1,
          total_pages: 5,
          created_lexemes: 2,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDictionaryScan(DICTIONARY_ID));

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
