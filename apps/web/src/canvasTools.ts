/** Interaction mode for the page-image control panel (BH-55/56). */
export type CanvasMode = "select" | "draw" | "erase";

export const CANVAS_MODE_LABELS: Record<CanvasMode, string> = {
  select: "Вибір",
  draw: "Виділити текст",
  erase: "Видалити",
};

export const ZOOM_MIN = 0.25;
export const ZOOM_MAX = 3;
export const ZOOM_STEP = 0.25;

export function clampZoom(value: number): number {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(value * 100) / 100));
}
