import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useArticleSchemaGeneration } from "./useArticleSchemaGeneration";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("useArticleSchemaGeneration", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("starts idle", () => {
    const { result } = renderHook(() => useArticleSchemaGeneration(DICTIONARY_ID));
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
          schema_id: "22222222-2222-2222-2222-222222222222",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useArticleSchemaGeneration(DICTIONARY_ID));

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
      schemaId: "22222222-2222-2222-2222-222222222222",
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
          error: "generation failed",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useArticleSchemaGeneration(DICTIONARY_ID));

    await act(async () => {
      await result.current.trigger();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(result.current.state).toEqual({
      status: "failed",
      message: "generation failed",
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

    const { result } = renderHook(() => useArticleSchemaGeneration(DICTIONARY_ID));

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
      .mockResolvedValue(jsonResponse(200, { task_id: "task-1", status: "running" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useArticleSchemaGeneration(DICTIONARY_ID));

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
