import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SessionListResponse } from "../api";
import { useSessions } from "./useSessions";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function sessionList(): SessionListResponse {
  return {
    sessions: [
      {
        id: "11111111-1111-1111-1111-111111111111",
        created_at: "2026-09-01T10:00:00Z",
        expires_at: "2026-09-01T22:00:00Z",
        user_agent: "Firefox",
        current: true,
      },
      {
        id: "22222222-2222-2222-2222-222222222222",
        created_at: "2026-08-31T10:00:00Z",
        expires_at: "2026-09-01T22:00:00Z",
        user_agent: "Safari",
        current: false,
      },
    ],
  };
}

describe("useSessions", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads sessions on mount", async () => {
    const list = sessionList();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, list)));

    const { result } = renderHook(() => useSessions());

    expect(result.current.state).toEqual({ status: "loading" });
    await waitFor(() =>
      expect(result.current.state).toEqual({
        status: "loaded",
        sessions: list.sessions,
      }),
    );
  });

  it("drops a session from the list after revoking it", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, sessionList()))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useSessions());
    await waitFor(() => expect(result.current.state.status).toBe("loaded"));

    await act(async () => {
      await result.current.revoke("22222222-2222-2222-2222-222222222222");
    });

    expect(result.current.state).toMatchObject({
      status: "loaded",
      sessions: [{ id: "11111111-1111-1111-1111-111111111111" }],
    });
  });

  it("keeps only the current session after revoking others", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, sessionList()))
      .mockResolvedValueOnce(jsonResponse(200, { revoked: 1 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useSessions());
    await waitFor(() => expect(result.current.state.status).toBe("loaded"));

    await act(async () => {
      await result.current.revokeOthers();
    });

    expect(result.current.state).toMatchObject({
      status: "loaded",
      sessions: [{ current: true }],
    });
  });

  it("surfaces a load error", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse(401, { code: "invalid_session", message: "Потрібна авторизація." }),
        ),
    );

    const { result } = renderHook(() => useSessions());

    await waitFor(() => expect(result.current.state.status).toBe("error"));
  });
});
