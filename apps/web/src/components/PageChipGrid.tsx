import { cn } from "@/lib/utils";

import type { PageProgress } from "../api";

/** Per-page chip grid shown in the page navigator's combobox popover
 * (extracted from `PageNavigator`, formerly the control panel, BH-57). */
export function PageChipGrid({
  pages,
  currentPage,
  onNavigate,
}: {
  pages: PageProgress[];
  currentPage: number;
  onNavigate: (pageNumber: number) => void;
}) {
  if (pages.length === 0) {
    return null;
  }

  return (
    <div
      role="group"
      aria-label="Сторінки словника"
      className="grid max-h-56 grid-cols-8 gap-2 overflow-y-auto overscroll-contain"
    >
      {pages.map((page) => {
        const isCurrent = page.page_number === currentPage;
        return (
          <button
            key={page.page_number}
            type="button"
            className={cn(
              "min-w-8 rounded-[0.35rem] border px-[0.4rem] py-1 text-center text-[0.8rem] tabular-nums transition-colors [contain-intrinsic-size:auto_1.8rem] [content-visibility:auto]",
              isCurrent
                ? "border-primary bg-primary font-[650] text-primary-foreground"
                : page.has_lexemes
                  ? "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/70"
                  : "border-border bg-transparent text-foreground hover:bg-accent",
            )}
            aria-current={isCurrent ? "page" : undefined}
            title={`Сторінка ${page.page_number}${isCurrent ? " — поточна" : ""}${page.has_lexemes ? " — опрацьована" : ""}`}
            onClick={() => onNavigate(page.page_number)}
          >
            {page.page_number}
          </button>
        );
      })}
    </div>
  );
}
