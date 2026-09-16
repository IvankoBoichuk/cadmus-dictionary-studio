import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { PageProgress } from "../api";
import { PageChipGrid } from "./PageChipGrid";

const PAGES: PageProgress[] = [
  { page_number: 1, has_lexemes: true },
  { page_number: 2, has_lexemes: false },
  { page_number: 3, has_lexemes: true },
];

function renderGrid(overrides: Partial<Parameters<typeof PageChipGrid>[0]> = {}) {
  return render(
    <PageChipGrid pages={PAGES} currentPage={2} onNavigate={vi.fn()} {...overrides} />,
  );
}

describe("PageChipGrid", () => {
  it("marks processed pages and navigates when a chip is clicked", () => {
    const onNavigate = vi.fn();
    renderGrid({ onNavigate });

    expect(screen.getByRole("button", { name: "1" })).toHaveAttribute(
      "title",
      "Сторінка 1 — опрацьована",
    );
    expect(screen.getByRole("button", { name: "2" })).toHaveAttribute(
      "title",
      "Сторінка 2 — поточна",
    );

    fireEvent.click(screen.getByRole("button", { name: "3" }));
    expect(onNavigate).toHaveBeenCalledWith(3);
  });

  it("marks the current page", () => {
    renderGrid({ currentPage: 2 });
    expect(screen.getByRole("button", { name: "2" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getByRole("button", { name: "1" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("renders nothing when there is no progress data", () => {
    const { container } = renderGrid({ pages: [] });
    expect(container).toBeEmptyDOMElement();
  });
});
