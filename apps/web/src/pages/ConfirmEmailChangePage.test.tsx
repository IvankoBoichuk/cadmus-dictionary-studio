import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConfirmEmailChangePage } from "./ConfirmEmailChangePage";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/confirm-email-change" element={<ConfirmEmailChangePage />} />
        <Route path="/login" element={<p>Сторінка входу</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ConfirmEmailChangePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("confirms the change when the token is valid", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { message: "Email оновлено." }));
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/confirm-email-change#token=good-token");

    await waitFor(() =>
      expect(screen.getByText("Email оновлено")).toBeInTheDocument(),
    );
    const [, requestInit] = fetchMock.mock.calls[0];
    expect(JSON.parse(requestInit.body)).toEqual({ token: "good-token" });
  });

  it("shows the server error for a spent token", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(400, {
          code: "used",
          message: "Це посилання вже було використано.",
        }),
      ),
    );

    renderAt("/confirm-email-change#token=used-token");

    await waitFor(() =>
      expect(
        screen.getByText("Це посилання вже було використано."),
      ).toBeInTheDocument(),
    );
  });

  it("reports a missing token without calling the API", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderAt("/confirm-email-change");

    expect(
      screen.getByText("У посиланні немає токена підтвердження."),
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
