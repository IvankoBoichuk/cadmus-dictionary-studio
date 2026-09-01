import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PageProgress } from "../api";
import { PageNavigator } from "./PageNavigator";

const PAGES: PageProgress[] = [
  { page_number: 1, has_lexemes: true },
  { page_number: 2, has_lexemes: false },
  { page_number: 3, has_lexemes: true },
];

function renderNav(overrides: Partial<Parameters<typeof PageNavigator>[0]> = {}) {
  return render(
    <PageNavigator
      pages={PAGES}
      currentPage={2}
      totalPages={3}
      onNavigate={vi.fn()}
      {...overrides}
    />,
  );
}

describe("PageNavigator", () => {
  it("shows the current page counter", () => {
    renderNav();
    expect(screen.getByText("Сторінка 2 / 3")).toBeInTheDocument();
  });

  it("calls onNavigate for prev / next", () => {
    const onNavigate = vi.fn();
    renderNav({ onNavigate });

    fireEvent.click(screen.getByRole("button", { name: "Наступна →" }));
    fireEvent.click(screen.getByRole("button", { name: "← Попередня" }));

    expect(onNavigate).toHaveBeenNthCalledWith(1, 3);
    expect(onNavigate).toHaveBeenNthCalledWith(2, 1);
  });

  it("disables prev on the first page", () => {
    renderNav({ currentPage: 1 });
    expect(screen.getByRole("button", { name: "← Попередня" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Наступна →" })).toBeEnabled();
  });

  it("disables next on the last page", () => {
    renderNav({ currentPage: 3 });
    expect(screen.getByRole("button", { name: "Наступна →" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "← Попередня" })).toBeEnabled();
  });

  it("marks processed pages and navigates when a chip is clicked", () => {
    const onNavigate = vi.fn();
    renderNav({ onNavigate });

    expect(screen.getByRole("button", { name: "1" })).toHaveAttribute(
      "title",
      "Сторінка 1 — опрацьована",
    );
    expect(screen.getByRole("button", { name: "2" })).toHaveAttribute(
      "title",
      "Сторінка 2",
    );

    fireEvent.click(screen.getByRole("button", { name: "3" }));
    expect(onNavigate).toHaveBeenCalledWith(3);
  });

  it("omits the chip grid when there is no progress data", () => {
    renderNav({ pages: [] });
    expect(screen.queryByRole("button", { name: "1" })).not.toBeInTheDocument();
    expect(screen.getByText("Сторінка 2 / 3")).toBeInTheDocument();
  });
});
