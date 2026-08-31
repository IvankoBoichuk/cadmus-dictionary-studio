import * as React from "react"

import { cn } from "@/lib/utils"

/*
 * Адаптовано під `.form-field textarea` зі старого styles.css (MIGRATION_PLAN.md, Крок 3):
 * та сама рамка/радіус/падінг/фон, що й `Input`, але `min-height: 5rem` і `resize: vertical`.
 */
function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "w-full min-w-0 min-h-[5rem] resize-y rounded-[0.55rem] border border-input bg-surface px-[0.8rem] py-[0.65rem] text-foreground outline-none transition-colors",
        "placeholder:text-muted-foreground",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-primary focus-visible:[outline:3px_solid_var(--color-ring-subtle)]",
        "aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
