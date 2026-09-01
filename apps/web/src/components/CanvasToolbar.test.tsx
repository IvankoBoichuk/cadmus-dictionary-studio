import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CanvasToolbar } from "./CanvasToolbar";

function renderToolbar(overrides: Partial<Parameters<typeof CanvasToolbar>[0]> = {}) {
  return render(
    <CanvasToolbar
      mode="select"
      onModeChange={vi.fn()}
      zoom={1}
      onZoomIn={vi.fn()}
      onZoomOut={vi.fn()}
      onZoomReset={vi.fn()}
      {...overrides}
    />,
  );
}

describe("CanvasToolbar", () => {
  it("marks the active tool and switches on click", () => {
    const onModeChange = vi.fn();
    renderToolbar({ mode: "select", onModeChange });

    expect(screen.getByRole("button", { name: "Вибір" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.click(screen.getByRole("button", { name: "Видалити" }));
    expect(onModeChange).toHaveBeenCalledWith("erase");

    fireEvent.click(screen.getByRole("button", { name: "Виділити текст" }));
    expect(onModeChange).toHaveBeenCalledWith("draw");
  });

  it("wires up the zoom controls and shows the current level", () => {
    const onZoomIn = vi.fn();
    const onZoomOut = vi.fn();
    const onZoomReset = vi.fn();
    renderToolbar({ zoom: 1.5, onZoomIn, onZoomOut, onZoomReset });

    expect(screen.getByText("150%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Збільшити" }));
    fireEvent.click(screen.getByRole("button", { name: "Зменшити" }));
    fireEvent.click(screen.getByRole("button", { name: "Скинути масштаб" }));

    expect(onZoomIn).toHaveBeenCalledTimes(1);
    expect(onZoomOut).toHaveBeenCalledTimes(1);
    expect(onZoomReset).toHaveBeenCalledTimes(1);
  });
});
