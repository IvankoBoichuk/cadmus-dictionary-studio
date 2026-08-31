import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

/*
 * Адаптовано під візуальну мову Cadmus (див. MIGRATION_PLAN.md, Крок 3).
 * Відповідники старих класів:
 *   глобальний <button>   → variant="default"
 *   .secondary-button     → variant="secondary"
 *   .danger-button        → variant="danger"
 *   .icon-button          → variant="secondary" size="icon"
 * Старі правила у styles.css поки лишаються (ізольовані в @layer legacy),
 * прибираються у Кроці 4.
 */
const buttonVariants = cva(
  "inline-flex shrink-0 cursor-pointer touch-manipulation items-center justify-center gap-2 rounded-full font-[650] whitespace-nowrap transition-[filter] duration-[120ms] ease-out outline-none focus-visible:[outline:3px_solid_var(--color-ring)] focus-visible:outline-offset-[3px] disabled:cursor-not-allowed disabled:pointer-events-none disabled:opacity-[0.68] aria-invalid:[outline-color:var(--color-destructive)] [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground not-disabled:hover:brightness-[0.93]",
        secondary:
          "bg-secondary text-secondary-foreground not-disabled:hover:brightness-[0.93]",
        danger:
          "bg-danger-soft text-danger-soft-foreground not-disabled:hover:brightness-[0.93]",
        destructive:
          "bg-destructive text-white not-disabled:hover:brightness-[0.93]",
        outline:
          "border border-input bg-background not-disabled:hover:bg-accent not-disabled:hover:text-accent-foreground",
        ghost:
          "not-disabled:hover:bg-accent not-disabled:hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "px-4 py-[0.7rem]",
        sm: "px-3 py-[0.4rem] text-sm",
        lg: "px-6 py-[0.85rem]",
        icon: "min-w-[2.4rem] p-[0.4rem] font-bold disabled:opacity-40",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
