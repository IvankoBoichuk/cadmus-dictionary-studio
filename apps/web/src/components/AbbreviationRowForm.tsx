import { Check, X } from "lucide-react";
import { type KeyboardEvent, useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TableCell, TableRow } from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import type { AbbreviationResponse } from "../api";
import { CATEGORY_OPTIONS } from "../abbreviationCategories";
import { useAbbreviationForm } from "../hooks/useAbbreviationForm";
import { useUnsavedChangesWarning } from "../hooks/useUnsavedChangesWarning";
import { LANGUAGE_OPTIONS } from "../languageOptions";

const LANGUAGE_NONE = "__none__";
const CELL_INPUT = "h-8 min-h-8 rounded-md px-2 py-1 text-[0.82rem]";
const CELL_TRIGGER = "h-8 min-h-8! rounded-md px-2 py-0 text-[0.82rem]";

function parseVariants(text: string): { value: string }[] {
  return text
    .split(/[,;]/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((value) => ({ value }));
}

/**
 * The "Додати / Редагувати скорочення" form rendered inline as table rows
 * (one field per column) — replaces the standalone `AbbreviationForm`.
 */
export function AbbreviationRowForm({
  dictionaryId,
  editing,
  onDone,
}: {
  dictionaryId: string;
  editing: AbbreviationResponse | null;
  onDone: (saved?: AbbreviationResponse) => void;
}) {
  const { form, onSubmit } = useAbbreviationForm(dictionaryId, editing, onDone);
  const noteId = useId();
  const unresolvedId = useId();
  const [variantsText, setVariantsText] = useState(
    editing?.variants.join(", ") ?? "",
  );

  useUnsavedChangesWarning(
    form.formState.isDirty && !form.formState.isSubmitting,
  );

  const errors = form.formState.errors;

  const submit = () => {
    form.setValue("variants", parseVariants(variantsText), { shouldDirty: true });
    void onSubmit();
  };

  const onEnter = (event: KeyboardEvent) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  };

  return (
    <>
      <TableRow className="bg-accent/40">
        <TableCell>
          <Input
            className={CELL_INPUT}
            aria-label="Скорочення"
            spellCheck={false}
            autoComplete="off"
            onKeyDown={onEnter}
            {...form.register("abbreviation")}
          />
          {errors.abbreviation && (
            <span className="field-error">{errors.abbreviation.message}</span>
          )}
        </TableCell>

        <TableCell>
          <Input
            className={CELL_INPUT}
            aria-label="Повна форма"
            onKeyDown={onEnter}
            {...form.register("full_form")}
          />
          {errors.full_form && (
            <span className="field-error">{errors.full_form.message}</span>
          )}
        </TableCell>

        <TableCell>
          <Select
            value={form.watch("category")}
            onValueChange={(value) =>
              form.setValue("category", value, { shouldDirty: true })
            }
          >
            <SelectTrigger
              size="sm"
              className={CELL_TRIGGER}
              aria-label="Категорія"
            >
              <SelectValue placeholder="Оберіть…" />
            </SelectTrigger>
            <SelectContent>
              {CATEGORY_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {errors.category && (
            <span className="field-error">{errors.category.message}</span>
          )}
        </TableCell>

        <TableCell>
          <Select
            value={form.watch("language_code") || LANGUAGE_NONE}
            onValueChange={(value) =>
              form.setValue(
                "language_code",
                value === LANGUAGE_NONE ? "" : value,
                { shouldDirty: true },
              )
            }
          >
            <SelectTrigger size="sm" className={CELL_TRIGGER} aria-label="Мова">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={LANGUAGE_NONE}>Не вказано</SelectItem>
              {LANGUAGE_OPTIONS.map((language) => (
                <SelectItem key={language.code} value={language.code}>
                  {language.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </TableCell>

        <TableCell>
          <Input
            className={CELL_INPUT}
            aria-label="Варіанти написання (через кому)"
            placeholder="напр. розм, р."
            value={variantsText}
            onChange={(event) => setVariantsText(event.target.value)}
            onKeyDown={onEnter}
          />
        </TableCell>

        <TableCell>
          <div className="flex gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon-sm"
                  type="button"
                  disabled={form.formState.isSubmitting}
                  onClick={submit}
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
        <TableCell colSpan={6}>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <span className="inline-flex items-center gap-2">
              <Checkbox
                id={unresolvedId}
                checked={form.watch("unresolved")}
                onCheckedChange={(checked) =>
                  form.setValue("unresolved", checked === true, {
                    shouldDirty: true,
                  })
                }
              />
              <Label htmlFor={unresolvedId} className="text-[0.82rem]">
                Розшифрування поки невідоме
              </Label>
            </span>
            <span className="flex min-w-[16rem] flex-1 items-center gap-2">
              <Label htmlFor={noteId} className="text-[0.82rem] whitespace-nowrap">
                Примітка
              </Label>
              <Input
                id={noteId}
                className={CELL_INPUT}
                onKeyDown={onEnter}
                {...form.register("note")}
              />
            </span>
          </div>
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
