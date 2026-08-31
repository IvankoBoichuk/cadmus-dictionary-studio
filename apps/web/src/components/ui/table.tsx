import * as React from "react"

import { cn } from "@/lib/utils"

/*
 * Адаптовано під `.abbreviation-table` / `.settlement-table` / `.member-table`
 * + `.table-wrapper` зі старого styles.css (MIGRATION_PLAN.md, Крок 3):
 *   wrapper: overflow-x auto + overscroll-x contain
 *   table:   width 100%, border-collapse
 *   th:      padding .6rem .75rem, text-align left, vertical-align top,
 *            color #33443d (--primary-strong), font-size .85rem, bold
 *   td:      те саме + overflow-wrap: anywhere
 *   рядок:   border-bottom 1px #d6dbd2 (у т.ч. останній — без [&_tr:last-child]:border-0)
 * Ховера рядка навмисно НЕ додаємо (у старому не було).
 */
function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div
      data-slot="table-container"
      className="relative w-full overflow-x-auto overscroll-x-contain"
    >
      <table
        data-slot="table"
        className={cn("w-full border-collapse", className)}
        {...props}
      />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return <thead data-slot="table-header" className={cn(className)} {...props} />
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody data-slot="table-body" className={cn(className)} {...props} />
}

function TableFooter({ className, ...props }: React.ComponentProps<"tfoot">) {
  return (
    <tfoot
      data-slot="table-footer"
      className={cn("border-t font-medium", className)}
      {...props}
    />
  )
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr data-slot="table-row" className={cn("border-b", className)} {...props} />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      data-slot="table-head"
      className={cn(
        "px-3 py-[0.6rem] text-left align-top text-[0.85rem] font-bold text-primary-strong [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return (
    <td
      data-slot="table-cell"
      className={cn(
        "px-3 py-[0.6rem] text-left align-top [overflow-wrap:anywhere] [&:has([role=checkbox])]:pr-0",
        className
      )}
      {...props}
    />
  )
}

function TableCaption({
  className,
  ...props
}: React.ComponentProps<"caption">) {
  return (
    <caption
      data-slot="table-caption"
      className={cn("mt-4 text-sm text-muted-foreground", className)}
      {...props}
    />
  )
}

export {
  Table,
  TableHeader,
  TableBody,
  TableFooter,
  TableHead,
  TableRow,
  TableCell,
  TableCaption,
}
