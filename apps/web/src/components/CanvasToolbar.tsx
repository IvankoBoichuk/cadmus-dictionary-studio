import {
  Eraser,
  Layers,
  Minus,
  MousePointer2,
  Plus,
  ScanText,
  SquareDashedMousePointer,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import type { PageProgress } from "../api";
import { CANVAS_MODE_LABELS, type CanvasMode } from "../canvasTools";
import { PageNavigator } from "./PageNavigator";

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
  currentPage,
  totalPages,
  pages,
  onNavigate,
  ocrRunning,
  onTriggerOcr,
  scanRunning,
  onTriggerScan,
}: {
  mode: CanvasMode;
  onModeChange: (mode: CanvasMode) => void;
  zoom: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
  currentPage: number;
  totalPages: number;
  pages: PageProgress[];
  onNavigate: (pageNumber: number) => void;
  ocrRunning: boolean;
  onTriggerOcr: () => void;
  scanRunning: boolean;
  onTriggerScan: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex gap-1" role="group" aria-label="Розпізнавання">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              size="icon-sm"
              variant="secondary"
              type="button"
              aria-label={
                ocrRunning ? "Розпізнаємо слова…" : "Автоматично знайти слова (OCR)"
              }
              onClick={onTriggerOcr}
              disabled={ocrRunning}
            >
              <ScanText aria-hidden="true" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {ocrRunning ? "Розпізнаємо слова…" : "Автоматично знайти слова (OCR)"}
          </TooltipContent>
        </Tooltip>
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              size="icon-sm"
              variant="secondary"
              type="button"
              aria-label={
                scanRunning
                  ? "Опрацьовуємо чергу…"
                  : "Запустити чергу OCR для всього словника"
              }
              onClick={onTriggerScan}
              disabled={scanRunning}
            >
              <Layers aria-hidden="true" />
            </Button>
          </TooltipTrigger>
          <TooltipContent>
            {scanRunning
              ? "Опрацьовуємо чергу…"
              : "Запустити чергу OCR для всього словника"}
          </TooltipContent>
        </Tooltip>
      </div>

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

      <div className="flex flex-1 justify-center">
        <PageNavigator
          currentPage={currentPage}
          totalPages={totalPages}
          pages={pages}
          onNavigate={onNavigate}
        />
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
        <Button
          type="button"
          size="sm"
          aria-label="Скинути масштаб"
          onClick={onZoomReset}
          variant="secondary"
        >
          {Math.round(zoom * 100)}%
        </Button>
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
