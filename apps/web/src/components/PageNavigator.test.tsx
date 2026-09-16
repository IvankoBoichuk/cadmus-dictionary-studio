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
      currentPage={2}
      totalPages={3}
      pages={PAGES}
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

  it("opens the page grid combobox from the counter and navigates from it", async () => {
    const onNavigate = vi.fn();
    renderNav({ onNavigate });

    expect(screen.queryByRole("button", { name: "3" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Сторінка 2 \/ 3/ }));

    const chip = await screen.findByRole("button", { name: "3" });
    fireEvent.click(chip);

    expect(onNavigate).toHaveBeenCalledWith(3);
  });
});
