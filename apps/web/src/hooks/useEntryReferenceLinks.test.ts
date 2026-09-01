import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type EntryReferenceLinkResponse } from "../api";
import { useEntryReferenceLinks } from "./useEntryReferenceLinks";

const ENTRY_ID = "33333333-3333-3333-3333-333333333333";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function link(
  overrides: Partial<EntryReferenceLinkResponse> = {},
): EntryReferenceLinkResponse {
  return {
    id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    entry_id: ENTRY_ID,
    reference_lemma_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    relation_type: "standard_equivalent",
    origin: "manual",
    validation_status: "confirmed",
    confidence: null,
    created_at: "2026-08-20T10:00:00Z",
    lemma: {
      id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      lemma: "хата",
      normalized_lemma: "хата",
      part_of_speech: "noun",
      key_tags: [],
      is_standard: true,
    },
    ...overrides,
  };
}

describe("useEntryReferenceLinks", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the entry's confirmed links", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, [link()]));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntryReferenceLinks(ENTRY_ID));

    await waitFor(() =>
      expect(result.current.state).toMatchObject({
        status: "loaded",
        links: [expect.objectContaining({ id: link().id })],
      }),
    );
  });

  it("appends a link created via add()", async () => {
    const created = link({ id: "cccccccc-cccc-cccc-cccc-cccccccccccc" });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, []))
      .mockResolvedValueOnce(jsonResponse(201, created));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntryReferenceLinks(ENTRY_ID));
    await waitFor(() => expect(result.current.state.status).toBe("loaded"));

    await act(async () => {
      await result.current.add(created.reference_lemma_id, "synonym");
    });

    expect(result.current.state).toMatchObject({
      status: "loaded",
      links: [expect.objectContaining({ id: created.id })],
    });
    const [, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      reference_lemma_id: created.reference_lemma_id,
      relation_type: "synonym",
    });
  });

  it("rethrows the API error when add() is rejected", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, []))
      .mockResolvedValueOnce(
        jsonResponse(422, {
          code: "non_standard_reference",
          message: "Для літературного відповідника виберіть нормативну лему.",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntryReferenceLinks(ENTRY_ID));
    await waitFor(() => expect(result.current.state.status).toBe("loaded"));

    await expect(
      act(async () => {
        await result.current.add("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", "standard_equivalent");
      }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("drops a link removed via remove()", async () => {
    const existing = link();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, [existing]))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntryReferenceLinks(ENTRY_ID));
    await waitFor(() => expect(result.current.state.status).toBe("loaded"));

    await act(async () => {
      await result.current.remove(existing.id);
    });

    expect(result.current.state).toMatchObject({ status: "loaded", links: [] });
  });
});
