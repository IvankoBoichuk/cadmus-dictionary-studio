import * as React from "react"
import { Progress as ProgressPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

/*
 * Адаптовано під `.progress-track` / `.progress-bar` зі старого styles.css
 * (MIGRATION_PLAN.md, Крок 3): висота .6rem, трек `--color-track` (#e3e8e0),
 * заповнення `--primary`, `transition: transform .2s`. Radix сам додає
 * role="progressbar" + aria-valuemin/max/now.
 */
function Progress({
  className,
  value,
  ...props
}: React.ComponentProps<typeof ProgressPrimitive.Root>) {
  return (
    <ProgressPrimitive.Root
      data-slot="progress"
      className={cn(
        "relative h-[0.6rem] w-full overflow-hidden rounded-full bg-track",
        className
      )}
      {...props}
    >
      <ProgressPrimitive.Indicator
        data-slot="progress-indicator"
        className="h-full w-full flex-1 bg-primary transition-transform duration-200 ease-linear"
        style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
      />
    </ProgressPrimitive.Root>
  )
}

export { Progress }
