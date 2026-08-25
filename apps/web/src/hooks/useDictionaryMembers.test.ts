import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MembersListResponse } from "../api";
import { useDictionaryMembers } from "./useDictionaryMembers";

const DICTIONARY_ID = "11111111-1111-1111-1111-111111111111";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function membersResponse(
  overrides: Partial<MembersListResponse> = {},
): MembersListResponse {
  return {
    my_role: "owner",
    members: [
      {
        user_id: "22222222-2222-2222-2222-222222222222",
        email: "owner@example.com",
        role: "owner",
        created_at: "2026-08-25T00:00:00Z",
        updated_at: "2026-08-25T00:00:00Z",
      },
    ],
    ...overrides,
  };
}

describe("useDictionaryMembers", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("loads members on mount", async () => {
    const response = membersResponse();
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, response));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDictionaryMembers(DICTIONARY_ID));

    expect(result.current.state).toEqual({ status: "loading" });
    await waitFor(() =>
      expect(result.current.state).toEqual({
        status: "loaded",
        members: response.members,
        myRole: "owner",
      }),
    );
  });

  it("surfaces a load error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(404, { code: "not_found", message: "Словник не знайдено." }),
      );
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDictionaryMembers(DICTIONARY_ID));

    await waitFor(() =>
      expect(result.current.state).toEqual({
        status: "error",
        message: "Словник не знайдено.",
      }),
    );
  });

  it("adds a member and appends it to the loaded list", async () => {
    const initial = membersResponse();
    const newMember = {
      user_id: "33333333-3333-3333-3333-333333333333",
      email: "editor@example.com",
      role: "editor" as const,
      created_at: "2026-08-25T01:00:00Z",
      updated_at: "2026-08-25T01:00:00Z",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, initial))
      .mockResolvedValueOnce(jsonResponse(201, newMember));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDictionaryMembers(DICTIONARY_ID));
    await waitFor(() => expect(result.current.state.status).toBe("loaded"));

    let added = false;
    await act(async () => {
      added = await result.current.add("editor@example.com", "editor");
    });

    expect(added).toBe(true);
    expect(result.current.state).toMatchObject({
      status: "loaded",
      members: [...initial.members, newMember],
    });
  });

  it("removes a member on delete", async () => {
    const initial = membersResponse({
      members: [
        ...membersResponse().members,
        {
          user_id: "44444444-4444-4444-4444-444444444444",
          email: "viewer@example.com",
          role: "viewer",
          created_at: "2026-08-25T00:00:00Z",
          updated_at: "2026-08-25T00:00:00Z",
        },
      ],
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, initial))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDictionaryMembers(DICTIONARY_ID));
    await waitFor(() => expect(result.current.state.status).toBe("loaded"));

    await act(async () => {
      await result.current.remove("44444444-4444-4444-4444-444444444444");
    });

    expect(result.current.state).toMatchObject({
      status: "loaded",
      members: initial.members.filter(
        (member) => member.user_id !== "44444444-4444-4444-4444-444444444444",
      ),
    });
  });
});
