import { describe, expect, it } from "vitest";

import {
  isRectLargeEnough,
  normalizeDragRect,
  resizeRect,
  scaleRect,
} from "./lexemeGeometry";

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

describe("resizeRect", () => {
  const rect = { x: 100, y: 100, width: 50, height: 40 };

  it("se handle grows width and height without moving the origin", () => {
    expect(resizeRect(rect, "se", 10, 5)).toEqual({
      x: 100,
      y: 100,
      width: 60,
      height: 45,
    });
  });

  it("nw handle moves the origin and shrinks width/height inversely", () => {
    expect(resizeRect(rect, "nw", 10, 5)).toEqual({
      x: 110,
      y: 105,
      width: 40,
      height: 35,
    });
  });

  it("e handle only changes width", () => {
    expect(resizeRect(rect, "e", 10, 999)).toEqual({
      x: 100,
      y: 100,
      width: 60,
      height: 40,
    });
  });

  it("n handle only changes the top edge and height", () => {
    expect(resizeRect(rect, "n", 999, 5)).toEqual({
      x: 100,
      y: 105,
      width: 50,
      height: 35,
    });
  });

  it("refuses to shrink a dimension past the minimum drag size", () => {
    expect(resizeRect(rect, "se", -100, -100)).toEqual(rect);
  });
});
