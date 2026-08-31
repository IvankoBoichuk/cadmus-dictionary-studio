/** Small `matchMedia` helpers, guarded for non-browser (test) environments. */

function matches(query: string): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(query).matches
  );
}

/** True when the viewer asked the OS to minimise non-essential motion. */
export function prefersReducedMotion(): boolean {
  return matches("(prefers-reduced-motion: reduce)");
}

/** True for a precise pointer (mouse/trackpad). Used to gate `autoFocus`, which
 * is disruptive on touch devices because it pops up the on-screen keyboard. */
export function isFinePointer(): boolean {
  return matches("(pointer: fine)");
}

/** `scrollIntoView` options that honour `prefers-reduced-motion`. */
export function scrollIntoViewOptions(
  options: ScrollIntoViewOptions = {},
): ScrollIntoViewOptions {
  return {
    ...options,
    behavior: prefersReducedMotion() ? "auto" : (options.behavior ?? "smooth"),
  };
}
