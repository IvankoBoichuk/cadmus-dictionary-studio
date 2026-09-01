import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ArticleSchemaResponse } from "../api";
import { useArticleSchemaEditor } from "./useArticleSchemaEditor";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function schema(overrides: Partial<ArticleSchemaResponse> = {}): ArticleSchemaResponse {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    dictionary_id: DICTIONARY_ID,
    version: 1,
    status: "ready",
    source_description: "",
    definition: { fields: [{ name: "headword", role: "headword", type: "string" }] },
    provider_name: null,
    error_message: null,
    presentation_formula: null,
    created_at: "2026-08-15T12:00:00Z",
    activated_at: null,
    ...overrides,
  };
}

describe("useArticleSchemaEditor", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("seeds the presentation formula from the initial version", () => {
    const { result } = renderHook(() =>
      useArticleSchemaEditor({
        dictionaryId: DICTIONARY_ID,
        initial: schema({ presentation_formula: "# {{ headword }}" }),
        onSaved: vi.fn(),
      }),
    );

    expect(result.current.presentationFormula).toBe("# {{ headword }}");
  });

  it("sends a trimmed presentation formula in the save payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, schema()));
    vi.stubGlobal("fetch", fetchMock);
    const onSaved = vi.fn();

    const { result } = renderHook(() =>
      useArticleSchemaEditor({
        dictionaryId: DICTIONARY_ID,
        initial: schema(),
        onSaved,
      }),
    );

    act(() => result.current.setPresentationFormula("  **{{ headword }}**  "));
    await act(async () => {
      await result.current.submit();
    });

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    const body = JSON.parse(
      (fetchMock.mock.calls[0]![1] as RequestInit).body as string,
    );
    expect(body.presentation_formula).toBe("**{{ headword }}**");
  });

  it("sends null when the formula is blank", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, schema()));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() =>
      useArticleSchemaEditor({
        dictionaryId: DICTIONARY_ID,
        initial: schema(),
        onSaved: vi.fn(),
      }),
    );

    await act(async () => {
      await result.current.submit();
    });

    const body = JSON.parse(
      (fetchMock.mock.calls[0]![1] as RequestInit).body as string,
    );
    expect(body.presentation_formula).toBeNull();
  });
});
