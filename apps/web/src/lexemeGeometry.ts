/** BH-54: pure pixel-rectangle math shared by the lexeme-selection canvas. */

export type Point = { x: number; y: number };

export type Rect = { x: number; y: number; width: number; height: number };

export const MIN_DRAG_SIZE = 6;
/** Below this many displayed pixels in either dimension, a drag is treated
 * as an accidental click rather than an intentional selection. */

/** Normalize two drag corners (in either order) into a top-left rectangle. */
export function normalizeDragRect(start: Point, current: Point): Rect {
  return {
    x: Math.min(start.x, current.x),
    y: Math.min(start.y, current.y),
    width: Math.abs(current.x - start.x),
    height: Math.abs(current.y - start.y),
  };
}

/** Multiply every dimension of ``rect`` by ``factor`` (unit conversion). */
export function scaleRect(rect: Rect, factor: number): Rect {
  return {
    x: rect.x * factor,
    y: rect.y * factor,
    width: rect.width * factor,
    height: rect.height * factor,
  };
}

export function isRectLargeEnough(rect: Rect): boolean {
  return rect.width >= MIN_DRAG_SIZE && rect.height >= MIN_DRAG_SIZE;
}

/** One of the 8 corner/edge resize handles on a selected lexeme box. */
export type HandleId = "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw";

export const HANDLES: readonly HandleId[] = [
  "nw",
  "n",
  "ne",
  "w",
  "e",
  "sw",
  "s",
  "se",
];

/**
 * Apply a handle drag delta to a rectangle, resizing from the edge(s) that
 * handle represents ("n"/"s" move only the top/bottom edge, "e"/"w" only
 * the left/right edge, corners move both). Refuses to shrink past
 * ``MIN_DRAG_SIZE`` rather than flipping the box inside out.
 */
export function resizeRect(rect: Rect, handle: HandleId, dx: number, dy: number): Rect {
  let { x, y, width, height } = rect;
  if (handle.includes("w")) {
    const newWidth = width - dx;
    if (newWidth >= MIN_DRAG_SIZE) {
      x += dx;
      width = newWidth;
    }
  }
  if (handle.includes("e")) {
    const newWidth = width + dx;
    if (newWidth >= MIN_DRAG_SIZE) width = newWidth;
  }
  if (handle.includes("n")) {
    const newHeight = height - dy;
    if (newHeight >= MIN_DRAG_SIZE) {
      y += dy;
      height = newHeight;
    }
  }
  if (handle.includes("s")) {
    const newHeight = height + dy;
    if (newHeight >= MIN_DRAG_SIZE) height = newHeight;
  }
  return { x, y, width, height };
}
