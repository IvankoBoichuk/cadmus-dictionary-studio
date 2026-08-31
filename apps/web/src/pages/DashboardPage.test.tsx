import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";

import type { AuthenticatedUser } from "../api";
import { AuthContext, type AuthContextValue } from "../authContext";
import { DashboardPage } from "./DashboardPage";

afterEach(() => {
  vi.unstubAllGlobals();
});

function authenticated(): AuthContextValue {
  return {
    session: {
      status: "authenticated",
      user: { email: "editor@example.com" } as AuthenticatedUser,
    },
    setAuthenticated: vi.fn(),
    setAnonymous: vi.fn(),
  };
}

function dictionaryEntry(overrides: Record<string, unknown> = {}) {
  return {
    id: "00000000-0000-0000-0000-000000000000",
    status: "draft",
    title: "Без назви",
    created_at: "2026-08-01T12:00:00Z",
    updated_at: "2026-08-01T12:00:00Z",
    readiness_blockers: [],
    missing_required_fields: [],
    contributors: [],
    language_codes: [],
    ...overrides,
  };
}

function renderDashboard(entries: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) === "/api/dictionaries") {
        return typeof entries === "number"
          ? new Response("nope", { status: entries })
          : new Response(JSON.stringify(entries), { status: 200 });
      }
      throw new Error(`Unexpected request: ${String(input)}`);
    }),
  );
  return render(
    <AuthContext.Provider value={authenticated()}>
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

it("summarises the dictionaries by lifecycle status", async () => {
  renderDashboard([
    dictionaryEntry({ id: "d1", status: "draft" }),
    dictionaryEntry({ id: "d2", status: "configured" }),
    dictionaryEntry({ id: "d3", status: "scanned" }),
  ]);

  const total = (await screen.findByText("Усього словників")).closest("div")!;
  expect(within(total).getByText("3")).toBeInTheDocument();

  const drafts = screen.getByText("Чернетки").closest("div")!;
  expect(within(drafts).getByText("1")).toBeInTheDocument();
  const ready = screen.getByText("Готові до обробки").closest("div")!;
  expect(within(ready).getByText("1")).toBeInTheDocument();
  const scanned = screen.getByText("Скановані").closest("div")!;
  expect(within(scanned).getByText("1")).toBeInTheDocument();
});

it("lists the most recently updated dictionaries first, linking each to its overview", async () => {
  renderDashboard([
    dictionaryEntry({
      id: "older",
      title: "Старіший словник",
      updated_at: "2026-08-10T09:00:00Z",
    }),
    dictionaryEntry({
      id: "newer",
      title: "Новіший словник",
      updated_at: "2026-08-20T09:00:00Z",
      readiness_blockers: [
        { code: "missing_metadata", message: "Заповніть метадані" },
        { code: "no_pages", message: "Додайте діапазони сторінок" },
      ],
    }),
  ]);

  await screen.findByText("Новіший словник");
  const rowLinks = screen
    .getAllByRole("link")
    .filter((link) =>
      /^\/dictionaries\/(?!new$)[^/]+$/.test(link.getAttribute("href") ?? ""),
    );
  expect(rowLinks.map((link) => link.textContent)).toEqual([
    "Новіший словник",
    "Старіший словник",
  ]);
  expect(rowLinks[0]).toHaveAttribute("href", "/dictionaries/newer");
  expect(screen.getByText("Потребує уваги: 2")).toBeInTheDocument();
});

it("shows an empty state with a call to action when there are no dictionaries", async () => {
  renderDashboard([]);

  expect(
    await screen.findByRole("heading", { name: "Ще немає словників" }),
  ).toBeInTheDocument();
  const addLinks = screen.getAllByRole("link", { name: "Додати словник" });
  expect(addLinks.length).toBeGreaterThan(0);
  for (const link of addLinks) {
    expect(link).toHaveAttribute("href", "/dictionaries/new");
  }
  expect(screen.queryByText("Усього словників")).not.toBeInTheDocument();
});

it("reports a load failure through an alert", async () => {
  renderDashboard(500);

  await waitFor(() =>
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Не вдалося завантажити словники",
    ),
  );
});
