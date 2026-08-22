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
