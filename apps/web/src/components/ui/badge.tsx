import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

/*
 * Відповідники старих класів (MIGRATION_PLAN.md, Крок 3):
 *   .badge / .badge--*         → <Badge size="default" variant=…>  (менший, weight 650)
 *   .status-badge / --draft/-- → <Badge size="lg" variant=…>       (більший, weight 600)
 * Варіанти кольорів = семантичні токени Cadmus:
 *   .badge--suggested/--status        → info
 *   .badge--ok/--confirmed/--complete → secondary (зелений на #eaf1ec)
 *   .badge--warning/--unresolved / .status-badge--draft → warning
 *   .badge--error                     → danger
 *   .status-badge--configured         → success
 * Старе `.badge { margin-left: .5rem }` НЕ в компоненті — додається `ml-2` на місці.
 */
const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center justify-center rounded-full font-[650] whitespace-nowrap",
  {
    variants: {
      variant: {
        secondary: "bg-secondary text-secondary-foreground",
        success: "bg-success text-success-foreground",
        warning: "bg-warning text-warning-foreground",
        info: "bg-info text-info-foreground",
        danger: "bg-danger-soft text-danger-soft-foreground",
      },
      size: {
        default: "px-2 py-[0.15rem] text-[0.78rem]",
        lg: "px-3 py-[0.3rem] text-[0.85rem] font-semibold",
      },
    },
    defaultVariants: {
      variant: "info",
      size: "default",
    },
  }
)

function Badge({
  className,
  variant,
  size,
  asChild = false,
  ...props
}: React.ComponentProps<"span"> &
  VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot.Root : "span"

  return (
    <Comp
      data-slot="badge"
      className={cn(badgeVariants({ variant, size }), className)}
      {...props}
    />
  )
}

export { Badge }
