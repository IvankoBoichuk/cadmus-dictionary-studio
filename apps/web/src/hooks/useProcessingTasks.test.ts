import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProcessingTaskResponse } from "../api";
import { useProcessingTasks } from "./useProcessingTasks";

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

describe("useProcessingTasks", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("loads the dictionary's tasks", async () => {
    const rows = [task(), task({ kind: "entry_extraction" })];
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, rows)));

    const { result } = renderHook(() => useProcessingTasks(DICTIONARY_ID));

    await waitFor(() =>
      expect(result.current.state).toMatchObject({
        status: "loaded",
        tasks: rows,
      }),
    );
  });

  it("keeps polling while a task is active, then stops", async () => {
    vi.useFakeTimers();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, [task({ status: "running" })]))
      .mockResolvedValueOnce(jsonResponse(200, [task({ status: "running" })]))
      .mockResolvedValue(jsonResponse(200, [task({ status: "succeeded" })]));
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useProcessingTasks(DICTIONARY_ID));

    await act(async () => {
      await Promise.resolve();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(4000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);

    // Third response has no active task -> the loop stops.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(8000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("adds the new task returned by retry()", async () => {
    const failed = task({ status: "failed", error: "boom" });
    const created = task({ status: "queued", retry_of_id: failed.id });
    let retried = false;
    const fetchMock = vi.fn((_input: unknown, init?: RequestInit) => {
      if (init?.method === "POST") {
        retried = true;
        return Promise.resolve(jsonResponse(202, created));
      }
      return Promise.resolve(
        jsonResponse(200, retried ? [created, failed] : [failed]),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useProcessingTasks(DICTIONARY_ID));
    await waitFor(() => expect(result.current.state.status).toBe("loaded"));

    await act(async () => {
      await result.current.retry(failed.id);
    });

    await waitFor(() => {
      const state = result.current.state;
      expect(state.status).toBe("loaded");
      if (state.status === "loaded") {
        expect(state.tasks.map((row) => row.id)).toContain(created.id);
      }
    });
    expect(
      fetchMock.mock.calls.some(
        ([, i]) => (i as RequestInit | undefined)?.method === "POST",
      ),
    ).toBe(true);
  });

  it("rethrows when retry fails", async () => {
    const failed = task({ status: "failed" });
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

    const { result } = renderHook(() => useProcessingTasks(DICTIONARY_ID));
    await waitFor(() => expect(result.current.state.status).toBe("loaded"));

    await expect(
      act(async () => {
        await result.current.retry(failed.id);
      }),
    ).rejects.toBeTruthy();
  });

  it("surfaces a load error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(500, { message: "збій" })),
    );

    const { result } = renderHook(() => useProcessingTasks(DICTIONARY_ID));

    await waitFor(() =>
      expect(result.current.state).toMatchObject({
        status: "error",
        message: "збій",
      }),
    );
  });
});
