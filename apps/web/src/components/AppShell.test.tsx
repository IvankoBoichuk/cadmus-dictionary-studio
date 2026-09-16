import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";

import type { AuthenticatedUser } from "../api";
import { AuthContext, type AuthContextValue } from "../authContext";
import { AppShell } from "./AppShell";

const SIDEBAR_COLLAPSED_KEY = "cadmus:sidebar-collapsed";

const USER: AuthenticatedUser = {
  id: "11111111-1111-1111-1111-111111111111",
  email: "researcher@example.com",
  name: "Дослідниця",
};

function authValue(): AuthContextValue {
  return {
    session: { status: "authenticated", user: USER },
    setAuthenticated: () => {},
    setAnonymous: () => {},
  };
}

function renderShell() {
  return render(
    <AuthContext.Provider value={authValue()}>
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<p>Вміст</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("AppShell sidebar collapse", () => {
  it("starts expanded and shows nav labels", () => {
    renderShell();
    expect(screen.getByText("Cadmus")).toBeVisible();
    expect(screen.getByText("Дашборд")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Згорнути бічну панель" }),
    ).toBeInTheDocument();
  });

  it("collapses on toggle and persists the choice", () => {
    renderShell();

    fireEvent.click(
      screen.getByRole("button", { name: "Згорнути бічну панель" }),
    );

    expect(
      screen.getByRole("button", { name: "Розгорнути бічну панель" }),
    ).toBeInTheDocument();
    expect(localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("1");
  });

  it("expands again on a second toggle", () => {
    renderShell();

    const toggle = () =>
      screen.getByRole("button", {
        name: /бічну панель/,
      });

    fireEvent.click(toggle());
    fireEvent.click(toggle());

    expect(
      screen.getByRole("button", { name: "Згорнути бічну панель" }),
    ).toBeInTheDocument();
    expect(localStorage.getItem(SIDEBAR_COLLAPSED_KEY)).toBe("0");
  });

  it("restores a collapsed state saved from a previous visit", () => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, "1");

    renderShell();

    expect(
      screen.getByRole("button", { name: "Розгорнути бічну панель" }),
    ).toBeInTheDocument();
  });
});
