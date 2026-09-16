import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

import type { PageProgress } from "../api";
import { PageChipGrid } from "./PageChipGrid";

/** Prev/next page navigation with a counter, for the canvas toolbar. The
 * counter opens a combobox popover with the per-page chip grid. */
export function PageNavigator({
  currentPage,
  totalPages,
  pages,
  onNavigate,
}: {
  currentPage: number;
  totalPages: number;
  pages: PageProgress[];
  onNavigate: (pageNumber: number) => void;
}) {
  const [isGridOpen, setIsGridOpen] = useState(false);

  return (
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
      <Popover open={isGridOpen} onOpenChange={setIsGridOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            className={cn(
              "flex min-w-32 items-center justify-center gap-1 rounded-md px-2 py-1 text-[0.85rem] font-[650] text-foreground tabular-nums",
              "hover:bg-accent focus-visible:[outline:2px_solid_var(--color-ring)]",
              "data-[state=open]:bg-accent",
            )}
          >
            Сторінка {currentPage} / {totalPages}
            <ChevronDown
              aria-hidden="true"
              className={cn(
                "size-3.5 shrink-0 text-muted-foreground transition-transform",
                isGridOpen && "rotate-180",
              )}
            />
          </button>
        </PopoverTrigger>
        <PopoverContent
          align="center"
          className="w-[min(90vw,22rem)] p-2"
        >
          <PageChipGrid
            pages={pages}
            currentPage={currentPage}
            onNavigate={(pageNumber) => {
              onNavigate(pageNumber);
              setIsGridOpen(false);
            }}
          />
        </PopoverContent>
      </Popover>
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
  );
}
