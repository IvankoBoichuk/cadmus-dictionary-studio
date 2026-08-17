import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SettlementSuggestionResponse } from "../api";
import { useSettlementSearch } from "./useSettlementSearch";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function suggestion(
  overrides: Partial<SettlementSuggestionResponse> = {},
): SettlementSuggestionResponse {
  return {
    settlement_id: "22222222-2222-2222-2222-222222222222",
    title: "Іванівка",
    category: "село",
    community_id: "33333333-3333-3333-3333-333333333333",
    community_name: "Львівська громада",
    region_id: "44444444-4444-4444-4444-444444444444",
    area_id: "55555555-5555-5555-5555-555555555555",
    ...overrides,
  };
}

describe("useSettlementSearch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stays idle until a filter is set (AC8)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useSettlementSearch(DICTIONARY_ID));

    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(result.current.state).toEqual({ status: "idle" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("debounces filter changes and returns results (AC8)", async () => {
    const results = [suggestion()];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, results));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useSettlementSearch(DICTIONARY_ID));

    act(() => {
      result.current.setFilters({ query: "Іван" });
    });

    expect(result.current.state).toEqual({ status: "idle" });

    await waitFor(
      () => expect(result.current.state).toMatchObject({ status: "results", results }),
      { timeout: 1000 },
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("query=%D0%86%D0%B2%D0%B0%D0%BD");
  });

  it("returns to idle once every filter is cleared", async () => {
    const results = [suggestion()];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, results));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useSettlementSearch(DICTIONARY_ID));

    act(() => {
      result.current.setFilters({ query: "Іван" });
    });
    await waitFor(() => expect(result.current.state.status).toBe("results"));

    act(() => {
      result.current.setFilters({});
    });

    await waitFor(() => expect(result.current.state).toEqual({ status: "idle" }));
  });

  it("surfaces a search error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(500, { message: "збій сервера" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useSettlementSearch(DICTIONARY_ID));

    act(() => {
      result.current.setFilters({ areaId: "55555555-5555-5555-5555-555555555555" });
    });

    await waitFor(() =>
      expect(result.current.state).toMatchObject({
        status: "error",
        message: "збій сервера",
      }),
    );
  });
});
