import { describe, expect, it } from "vitest";

import { isRectLargeEnough, normalizeDragRect, scaleRect } from "./lexemeGeometry";

describe("normalizeDragRect", () => {
  it("normalizes a drag drawn top-left to bottom-right", () => {
    expect(normalizeDragRect({ x: 10, y: 20 }, { x: 50, y: 60 })).toEqual({
      x: 10,
      y: 20,
      width: 40,
      height: 40,
    });
  });

  it("normalizes a drag drawn bottom-right to top-left", () => {
    expect(normalizeDragRect({ x: 50, y: 60 }, { x: 10, y: 20 })).toEqual({
      x: 10,
      y: 20,
      width: 40,
      height: 40,
    });
  });
});

describe("scaleRect", () => {
  it("scales every dimension by the given factor", () => {
    expect(scaleRect({ x: 10, y: 20, width: 30, height: 40 }, 2)).toEqual({
      x: 20,
      y: 40,
      width: 60,
      height: 80,
    });
  });
});

describe("isRectLargeEnough", () => {
  it("rejects a rectangle smaller than the minimum drag size", () => {
    expect(isRectLargeEnough({ x: 0, y: 0, width: 3, height: 3 })).toBe(false);
  });

  it("accepts a rectangle at or above the minimum drag size", () => {
    expect(isRectLargeEnough({ x: 0, y: 0, width: 10, height: 10 })).toBe(true);
  });
});
