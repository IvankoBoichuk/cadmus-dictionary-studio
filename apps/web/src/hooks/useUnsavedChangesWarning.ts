import { useEffect } from "react";

/**
 * Prompts the browser's native "leave site?" dialog while `enabled` is true, so
 * a half-filled form isn't lost to an accidental reload or tab close.
 *
 * This only covers full-page navigation; in-app `<Link>` navigation is not
 * intercepted (react-router v7 would need a data router + `useBlocker` for that).
 */
export function useUnsavedChangesWarning(enabled: boolean): void {
  useEffect(() => {
    if (!enabled) return;

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [enabled]);
}
