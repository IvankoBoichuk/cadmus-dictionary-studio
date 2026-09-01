import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ScanProgressBar } from "./ScanProgressBar";

function indicatorTransform(container: HTMLElement): string {
  const indicator = container.querySelector<HTMLElement>(
    '[data-slot="progress-indicator"]',
  );
  return indicator?.style.transform ?? "";
}

describe("ScanProgressBar", () => {
  it("shows the processed / total count (AC2)", () => {
    render(<ScanProgressBar processed={2} total={3} />);

    expect(screen.getByText("Опрацьовано 2 / 3 сторінок")).toBeInTheDocument();
  });

  it("reflects progress as a percentage on the progress bar", () => {
    const { container } = render(<ScanProgressBar processed={1} total={4} />);

    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    expect(indicatorTransform(container)).toBe("translateX(-75%)");
  });

  it("shows 0 % when there are no pages", () => {
    const { container } = render(<ScanProgressBar processed={0} total={0} />);

    expect(screen.getByText("Опрацьовано 0 / 0 сторінок")).toBeInTheDocument();
    expect(indicatorTransform(container)).toBe("translateX(-100%)");
  });
});
