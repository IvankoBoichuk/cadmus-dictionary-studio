import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiStatus } from "./ApiStatus";

describe("ApiStatus", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("shows that the API is available after a successful health check", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<ApiStatus />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Перевіряємо доступність",
    );
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Доступний"),
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
  });

  it("shows an unavailable state when the health check fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    render(<ApiStatus />);

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Недоступний"),
    );
    expect(
      screen.getByRole("button", { name: "Спробувати знову" }),
    ).toBeInTheDocument();
  });

  it("rejects an unexpected health payload", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ status: "degraded" }), { status: 200 }),
      ),
    );

    render(<ApiStatus />);

    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Недоступний"),
    );
  });

  it("lets the user retry an unavailable API", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<ApiStatus />);

    const retryButton = await screen.findByRole("button", {
      name: "Спробувати знову",
    });
    fireEvent.click(retryButton);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Перевіряємо доступність",
    );
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent("Доступний"),
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
