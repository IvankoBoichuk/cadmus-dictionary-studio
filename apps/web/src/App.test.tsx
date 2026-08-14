import { render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { App } from "./App";

afterEach(() => {
  window.history.replaceState({}, "", "/");
  vi.unstubAllGlobals();
});

it("renders the base application layout", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
    ),
  );

  render(<App />);

  expect(
    screen.getByRole("heading", { name: "Cadmus Dictionary Studio" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Cadmus — головна" })).toHaveAttribute(
    "href",
    "/",
  );
});

it("renders a not-found route", () => {
  window.history.replaceState({}, "", "/missing");

  render(<App />);

  expect(
    screen.getByRole("heading", { name: "Сторінку не знайдено" }),
  ).toBeInTheDocument();
});
