import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import type { PageProgress } from "../api";

/** Page navigation for the control panel: prev/next, a counter, and the
 * per-page chip grid (extracted from the former `ScanProgressBar`, BH-57). */
export function PageNavigator({
  pages,
  currentPage,
  totalPages,
  onNavigate,
}: {
  pages: PageProgress[];
  currentPage: number;
  totalPages: number;
  onNavigate: (pageNumber: number) => void;
}) {
  return (
    <div className="grid gap-2">
      <div className="flex items-center gap-3">
        <Button
          variant="secondary"
          size="sm"
          type="button"
          onClick={() => onNavigate(currentPage - 1)}
          disabled={currentPage <= 1}
        >
          ← Попередня
        </Button>
        <span
          className="min-w-32 text-center text-[0.85rem] font-[650] tabular-nums"
          role="status"
        >
          Сторінка {currentPage} / {totalPages}
        </span>
        <Button
          variant="secondary"
          size="sm"
          type="button"
          onClick={() => onNavigate(currentPage + 1)}
          disabled={currentPage >= totalPages}
        >
          Наступна →
        </Button>
      </div>

      {pages.length > 0 && (
        <div className="flex max-h-20 flex-wrap gap-[0.3rem] overflow-y-auto overscroll-contain">
          {pages.map((page) => (
            <button
              key={page.page_number}
              type="button"
              className={cn(
                "min-w-8 rounded-[0.35rem] border bg-surface px-[0.4rem] py-1 text-center text-[0.8rem] text-foreground tabular-nums [contain-intrinsic-size:auto_1.8rem] [content-visibility:auto] aria-[current=page]:[outline:2px_solid_var(--color-selected)] aria-[current=page]:outline-offset-1",
                page.has_lexemes &&
                  "border-primary bg-secondary font-[650] text-primary",
              )}
              aria-current={
                page.page_number === currentPage ? "page" : undefined
              }
              title={`Сторінка ${page.page_number}${page.has_lexemes ? " — опрацьована" : ""}`}
              onClick={() => onNavigate(page.page_number)}
            >
              {page.page_number}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
