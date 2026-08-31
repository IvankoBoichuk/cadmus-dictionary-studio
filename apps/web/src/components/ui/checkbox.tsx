import * as React from "react"
import { CheckIcon } from "lucide-react"
import { Checkbox as CheckboxPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

/*
 * Старий код мав звичайний нативний <input type="checkbox"> без власних стилів.
 * Тут — узгоджений із рештою полів вигляд: рамка --input, стан "checked" → --primary,
 * фокус як в Input. `bg-surface p-0` обов'язкові — Root це <button>, який поки
 * ловить старе глобальне `button { background:#245847; padding:.7rem 1rem }` з @layer legacy.
 */
function Checkbox({
  className,
  ...props
}: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer size-4 shrink-0 rounded-[4px] border border-input bg-surface p-0 transition-colors outline-none",
        "focus-visible:border-primary focus-visible:[outline:3px_solid_var(--color-ring-subtle)]",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive",
        "data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
        className
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className="grid place-content-center text-current transition-none"
      >
        <CheckIcon className="size-3.5" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
