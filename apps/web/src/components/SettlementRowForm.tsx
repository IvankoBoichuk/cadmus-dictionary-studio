import { Check, Search, X } from "lucide-react";
import { type KeyboardEvent, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { TableCell, TableRow } from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import type { SettlementMappingResponse } from "../api";
import { useSettlementForm } from "../hooks/useSettlementForm";
import { useUnsavedChangesWarning } from "../hooks/useUnsavedChangesWarning";
import { SettlementSearchCombobox } from "./SettlementSearchCombobox";

const STATUS_LABELS: Record<SettlementMappingResponse["status"], string> = {
  unresolved: "не зіставлено",
  suggested: "запропоновано",
  confirmed: "підтверджено",
};

const STATUS_BADGE_VARIANT: Record<
  SettlementMappingResponse["status"],
  "warning" | "info" | "secondary"
> = {
  unresolved: "warning",
  suggested: "info",
  confirmed: "secondary",
};

const CELL_INPUT = "h-8 min-h-8 rounded-md px-2 py-1 text-[0.82rem]";

/**
 * The "Додати / Редагувати географічну мітку" form rendered inline as table
 * rows (one field per column) — replaces the standalone `SettlementForm`.
 */
export function SettlementRowForm({
  dictionaryId,
  editing,
  onDone,
}: {
  dictionaryId: string;
  editing: SettlementMappingResponse | null;
  onDone: (saved?: SettlementMappingResponse) => void;
}) {
  const { form, onSubmit, applySuggestion, clearSuggestion } = useSettlementForm(
    dictionaryId,
    editing,
    onDone,
  );
  const [searchOpen, setSearchOpen] = useState(false);
  const [pickedCommunity, setPickedCommunity] = useState<string | null>(
    editing?.community_name ?? null,
  );

  useUnsavedChangesWarning(
    form.formState.isDirty && !form.formState.isSubmitting,
  );

  const settlementId = form.watch("settlement_id");
  const errors = form.formState.errors;

  const onEnter = (event: KeyboardEvent) => {
    if (event.key === "Enter") {
      event.preventDefault();
      void onSubmit();
    }
  };

  return (
    <>
      <TableRow className="bg-accent/40">
        <TableCell>
          <Input
            className={CELL_INPUT}
            aria-label="Позначка з оригіналу"
            onKeyDown={onEnter}
            {...form.register("source_label")}
          />
          {errors.source_label && (
            <span className="field-error">{errors.source_label.message}</span>
          )}
        </TableCell>

        <TableCell>
          <div className="flex items-center gap-1">
            <Input
              className={CELL_INPUT}
              aria-label="Сучасна назва"
              onKeyDown={onEnter}
              {...form.register("modern_settlement_name")}
            />
            <Popover open={searchOpen} onOpenChange={setSearchOpen}>
              <PopoverTrigger asChild>
                <Button
                  size="icon-sm"
                  variant="secondary"
                  type="button"
                  aria-label="Знайти сучасний населений пункт"
                >
                  <Search aria-hidden="true" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="max-h-[70vh] w-[min(90vw,26rem)] overflow-y-auto">
                <SettlementSearchCombobox
                  dictionaryId={dictionaryId}
                  onSelect={(suggestion) => {
                    applySuggestion(suggestion);
                    setPickedCommunity(suggestion.community_name);
                    setSearchOpen(false);
                  }}
                />
              </PopoverContent>
            </Popover>
            {settlementId && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="icon-sm"
                    variant="secondary"
                    type="button"
                    onClick={() => {
                      clearSuggestion();
                      setPickedCommunity(null);
                    }}
                    aria-label="Скасувати зіставлення"
                  >
                    <X aria-hidden="true" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Скасувати зіставлення</TooltipContent>
              </Tooltip>
            )}
          </div>
        </TableCell>

        <TableCell className="text-muted-foreground">
          {editing?.community_name ?? pickedCommunity ?? "—"}
        </TableCell>

        <TableCell>
          {editing ? (
            <Badge variant={STATUS_BADGE_VARIANT[editing.status]}>
              {STATUS_LABELS[editing.status]}
            </Badge>
          ) : (
            <span className="text-muted-foreground">—</span>
          )}
        </TableCell>

        <TableCell>
          <div className="flex gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon-sm"
                  type="button"
                  disabled={form.formState.isSubmitting}
                  onClick={() => void onSubmit()}
                  aria-label="Зберегти"
                >
                  <Check aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Зберегти</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon-sm"
                  variant="secondary"
                  type="button"
                  onClick={() => onDone()}
                  aria-label="Скасувати"
                >
                  <X aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Скасувати</TooltipContent>
            </Tooltip>
          </div>
        </TableCell>
      </TableRow>

      <TableRow className="bg-accent/40">
        <TableCell colSpan={5}>
          <span className="flex min-w-[16rem] items-center gap-2">
            <span className="text-[0.82rem] whitespace-nowrap text-muted-foreground">
              Примітка з оригіналу
            </span>
            <Input
              className={CELL_INPUT}
              aria-label="Примітка з оригіналу"
              onKeyDown={onEnter}
              {...form.register("source_note")}
            />
          </span>
          {errors.root && (
            <p className="field-error mt-1" role="alert">
              {errors.root.message}
            </p>
          )}
        </TableCell>
      </TableRow>
    </>
  );
}
