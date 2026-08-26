import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useEntryExtraction } from "./useEntryExtraction";

const ENTRY_ID = "33333333-3333-3333-3333-333333333333";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("useEntryExtraction", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("starts idle", () => {
    const { result } = renderHook(() => useEntryExtraction(ENTRY_ID));
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
          created_fields: 4,
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntryExtraction(ENTRY_ID));

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
      createdFields: 4,
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
          error: "extraction failed",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntryExtraction(ENTRY_ID));

    await act(async () => {
      await result.current.trigger();
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });

    expect(result.current.state).toEqual({
      status: "failed",
      message: "extraction failed",
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
        jsonResponse(404, { code: "not_found", message: "Статтю не знайдено." }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntryExtraction(ENTRY_ID));

    await act(async () => {
      await result.current.trigger();
    });

    expect(result.current.state).toEqual({
      status: "failed",
      message: "Статтю не знайдено.",
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });
    expect(fetchMock.mock.calls.length).toBe(1);
  });
});
