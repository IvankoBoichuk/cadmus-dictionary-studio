import { Eraser, Minus, MousePointer2, Plus, SquareDashedMousePointer } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { CANVAS_MODE_LABELS, type CanvasMode } from "../canvasTools";

const TOOL_ICONS: Record<CanvasMode, typeof MousePointer2> = {
  select: MousePointer2,
  draw: SquareDashedMousePointer,
  erase: Eraser,
};

const TOOLS: CanvasMode[] = ["select", "draw", "erase"];

/** Toolbar for the page-image control panel: mode switch + zoom controls. */
export function CanvasToolbar({
  mode,
  onModeChange,
  zoom,
  onZoomIn,
  onZoomOut,
  onZoomReset,
}: {
  mode: CanvasMode;
  onModeChange: (mode: CanvasMode) => void;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex gap-1" role="group" aria-label="Інструменти">
        {TOOLS.map((tool) => {
          const Icon = TOOL_ICONS[tool];
          const active = mode === tool;
          return (
            <Tooltip key={tool}>
              <TooltipTrigger asChild>
                <Button
                  size="icon-sm"
                  variant={active ? "default" : "secondary"}
                  type="button"
                  aria-pressed={active}
                  aria-label={CANVAS_MODE_LABELS[tool]}
                  onClick={() => onModeChange(tool)}
                >
                  <Icon aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>{CANVAS_MODE_LABELS[tool]}</TooltipContent>
            </Tooltip>
          );
        })}
      </div>

      <div
        className="ml-auto flex items-center gap-1"
        role="group"
        aria-label="Масштаб"
      >
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              size="icon-sm"
              variant="secondary"
              type="button"
              aria-label="Зменшити"
              onClick={onZoomOut}
            >
              <Minus aria-hidden="true" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Зменшити</TooltipContent>
        </Tooltip>
        <button
          type="button"
          aria-label="Скинути масштаб"
          onClick={onZoomReset}
          className={cn(
            "min-w-[3.25rem] rounded-md px-1 py-1 text-center text-[0.82rem] font-[650] tabular-nums",
            "hover:bg-accent focus-visible:[outline:2px_solid_var(--color-ring)]",
          )}
        >
          {Math.round(zoom * 100)}%
        </button>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              size="icon-sm"
              variant="secondary"
              type="button"
              aria-label="Збільшити"
              onClick={onZoomIn}
            >
              <Plus aria-hidden="true" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>Збільшити</TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}
