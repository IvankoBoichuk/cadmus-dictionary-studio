import * as React from "react"

import { cn } from "@/lib/utils"

/*
 * Адаптовано під `.form-field input` зі старого styles.css (MIGRATION_PLAN.md, Крок 3):
 *   border 1px #9aa7a1 (--input), radius .55rem, min-height 2.9rem, padding .65rem .8rem,
 *   фон #fff, шрифт успадкований; focus → border #245847 + outline 3px #dcebe5 (--ring-subtle);
 *   aria-invalid → border --destructive (зведено з давнього #b43c2d, рішення №3 у плані).
 */
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "w-full min-w-0 min-h-[2.9rem] rounded-[0.55rem] border border-input bg-surface px-[0.8rem] py-[0.65rem] text-foreground outline-none transition-colors",
        "selection:bg-primary selection:text-primary-foreground placeholder:text-muted-foreground",
        "file:mr-3 file:inline-flex file:border-0 file:bg-transparent file:font-[650] file:text-foreground",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-primary focus-visible:[outline:3px_solid_var(--color-ring-subtle)]",
        "aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Input }
