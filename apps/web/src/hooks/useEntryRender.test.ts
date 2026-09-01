import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useEntryRender } from "./useEntryRender";

const ENTRY_ID = "33333333-3333-3333-3333-333333333333";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("useEntryRender", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads the rendered Markdown", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, { markdown: "# кіт", reason: null, error: null }),
      ),
    );

    const { result } = renderHook(() => useEntryRender(ENTRY_ID));

    await waitFor(() =>
      expect(result.current.state).toEqual({
        status: "loaded",
        markdown: "# кіт",
        reason: null,
        error: null,
      }),
    );
  });

  it("surfaces a template error without becoming an error state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(200, {
          markdown: null,
          reason: "template_error",
          error: "unexpected end of template",
        }),
      ),
    );

    const { result } = renderHook(() => useEntryRender(ENTRY_ID));

    await waitFor(() =>
      expect(result.current.state).toMatchObject({
        status: "loaded",
        markdown: null,
        reason: "template_error",
        error: "unexpected end of template",
      }),
    );
  });

  it("re-fetches when reload() is called", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(200, { markdown: "v1", reason: null, error: null }),
      )
      .mockResolvedValueOnce(
        jsonResponse(200, { markdown: "v2", reason: null, error: null }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntryRender(ENTRY_ID));
    await waitFor(() =>
      expect(result.current.state).toMatchObject({ markdown: "v1" }),
    );

    result.current.reload();

    await waitFor(() =>
      expect(result.current.state).toMatchObject({ markdown: "v2" }),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
