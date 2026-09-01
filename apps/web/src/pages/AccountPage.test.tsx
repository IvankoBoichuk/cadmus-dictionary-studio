import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AuthenticatedUser } from "../api";
import { AuthContext, type AuthContextValue } from "../authContext";
import { AccountPage } from "./AccountPage";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const USER: AuthenticatedUser = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "researcher@example.com",
  name: null,
};

function authValue(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    session: { status: "authenticated", user: USER },
    setAuthenticated: vi.fn(),
    setAnonymous: vi.fn(),
    ...overrides,
  };
}

const SESSIONS = {
  sessions: [
    {
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      created_at: "2026-09-01T10:00:00Z",
      expires_at: "2026-09-01T22:00:00Z",
      user_agent: "Firefox on Linux",
      current: true,
    },
    {
      id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
      created_at: "2026-08-30T09:00:00Z",
      expires_at: "2026-09-01T22:00:00Z",
      user_agent: "Safari on iPhone",
      current: false,
    },
  ],
};

function renderPage(auth: AuthContextValue = authValue()) {
  return render(
    <AuthContext.Provider value={auth}>
      <MemoryRouter>
        <AccountPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe("AccountPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows the account sections and the current email", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, SESSIONS)));

    renderPage();

    expect(
      screen.getByRole("heading", { name: "Мій профіль" }),
    ).toBeInTheDocument();
    expect(screen.getByText("researcher@example.com")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Активні сесії" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("Firefox on Linux")).toBeInTheDocument(),
    );
  });

  it("saves a new display name and updates the session", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, SESSIONS))
      .mockResolvedValueOnce(
        jsonResponse(200, { ...USER, name: "Ада Лавлейс" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const auth = authValue();

    renderPage(auth);

    fireEvent.change(screen.getByLabelText("Ім’я"), {
      target: { value: "Ада Лавлейс" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Зберегти" }));

    await waitFor(() =>
      expect(screen.getByText("Ім’я збережено.")).toBeInTheDocument(),
    );
    const patchCall = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "PATCH",
    );
    expect(patchCall?.[0]).toBe("/api/auth/account");
    expect(JSON.parse(patchCall?.[1].body)).toEqual({ name: "Ада Лавлейс" });
    expect(auth.setAuthenticated).toHaveBeenCalledWith({
      ...USER,
      name: "Ада Лавлейс",
    });
  });

  it("validates the password confirmation before calling the API", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, SESSIONS));
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    fireEvent.change(screen.getByLabelText("Новий пароль"), {
      target: { value: "a-brand-new-password" },
    });
    fireEvent.change(screen.getByLabelText("Підтвердження пароля"), {
      target: { value: "different-value" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Змінити пароль" }));

    await waitFor(() =>
      expect(screen.getByText("Паролі не збігаються.")).toBeInTheDocument(),
    );
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "POST"),
    ).toBe(false);
  });

  it("revokes another device and removes it from the list", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(200, SESSIONS))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    renderPage();

    await waitFor(() =>
      expect(screen.getByText("Safari on iPhone")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Вийти" }));

    await waitFor(() =>
      expect(screen.queryByText("Safari on iPhone")).not.toBeInTheDocument(),
    );
    const deleteCall = fetchMock.mock.calls.find(
      ([, init]) => init?.method === "DELETE",
    );
    expect(deleteCall?.[0]).toBe(
      "/api/auth/sessions/bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    );
  });
});
