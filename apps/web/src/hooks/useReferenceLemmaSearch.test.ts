import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ReferenceLemmaResponse } from "../api";
import { useReferenceLemmaSearch } from "./useReferenceLemmaSearch";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function lemma(overrides: Partial<ReferenceLemmaResponse> = {}): ReferenceLemmaResponse {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    lemma: "хата",
    normalized_lemma: "хата",
    part_of_speech: "noun",
    key_tags: ["inanim"],
    is_standard: true,
    ...overrides,
  };
}

describe("useReferenceLemmaSearch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("stays idle until a non-blank query is set", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReferenceLemmaSearch("vesum"));

    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(result.current.state).toEqual({ status: "idle" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("debounces the query and returns results with the standard-only filter", async () => {
    const results = [lemma()];
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, results));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReferenceLemmaSearch("vesum"));

    act(() => result.current.setQuery("хат"));
    expect(result.current.state).toEqual({ status: "idle" });

    await waitFor(() =>
      expect(result.current.state).toMatchObject({ status: "results", results }),
    );
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toContain("/reference-lexicons/vesum/lemmas?");
    expect(url).toContain("standard_only=true");
    expect(url).toContain("limit=20");
  });

  it("re-queries when the standard-only toggle changes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReferenceLemmaSearch("vesum"));

    act(() => result.current.setQuery("хат"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    act(() => result.current.setStandardOnly(false));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const [url] = fetchMock.mock.calls[1] as [string];
    expect(url).toContain("standard_only=false");
  });

  it("surfaces a search error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(500, { message: "збій сервера" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReferenceLemmaSearch("vesum"));

    act(() => result.current.setQuery("хат"));

    await waitFor(() =>
      expect(result.current.state).toMatchObject({
        status: "error",
        message: "збій сервера",
      }),
    );
  });
});
