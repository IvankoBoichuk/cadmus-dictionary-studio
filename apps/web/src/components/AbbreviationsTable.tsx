import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import type { AbbreviationResponse } from "../api";
import { CATEGORY_LABELS } from "../abbreviationCategories";
import { LANGUAGE_OPTIONS } from "../languageOptions";
import { AbbreviationRowForm } from "./AbbreviationRowForm";

const LANGUAGE_NAMES: Record<string, string> = Object.fromEntries(
  LANGUAGE_OPTIONS.map((language) => [language.code, language.name]),
);

const COMPACT =
  "text-[0.82rem] [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1 [&_td]:align-middle";

export function AbbreviationsTable({
  dictionaryId,
  abbreviations,
  onSaved,
  onDelete,
  deleteState,
}: {
  dictionaryId: string;
  abbreviations: AbbreviationResponse[];
  onSaved: (saved: AbbreviationResponse) => void;
  onDelete: (item: AbbreviationResponse) => void;
  deleteState: Record<
    string,
    { pending: boolean; error: string | undefined } | undefined
  >;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  return (
    <Table className={COMPACT}>
      <caption className="sr-only">Список скорочень словника</caption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Скорочення</TableHead>
          <TableHead scope="col">Повна форма</TableHead>
          <TableHead scope="col">Категорія</TableHead>
          <TableHead scope="col">Мова</TableHead>
          <TableHead scope="col">Варіанти</TableHead>
          <TableHead scope="col">Дії</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {abbreviations.length === 0 && !adding && (
          <TableRow>
            <TableCell colSpan={6} className="text-muted-foreground">
              Скорочень ще немає. Натисніть + щоб додати перше.
            </TableCell>
          </TableRow>
        )}

        {abbreviations.map((item) => {
          const rowDeleteState = deleteState[item.id];
          if (editingId === item.id) {
            return (
              <AbbreviationRowForm
                key={item.id}
                dictionaryId={dictionaryId}
                editing={item}
                onDone={(saved) => {
                  if (saved) onSaved(saved);
                  setEditingId(null);
                }}
              />
            );
          }
          return (
            <TableRow key={item.id}>
              <TableCell>
                {item.abbreviation}
                {item.unresolved && (
                  <Badge className="ml-2" variant="warning">
                    нерозшифроване
                  </Badge>
                )}
              </TableCell>
              <TableCell>{item.full_form ?? "—"}</TableCell>
              <TableCell>{CATEGORY_LABELS[item.category]}</TableCell>
              <TableCell>
                {item.language_code
                  ? (LANGUAGE_NAMES[item.language_code] ?? item.language_code)
                  : "—"}
              </TableCell>
              <TableCell>
                {item.variants.length > 0 ? item.variants.join(", ") : "—"}
              </TableCell>
              <TableCell>
                <div className="flex gap-1">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        size="icon-sm"
                        variant="secondary"
                        type="button"
                        onClick={() => setEditingId(item.id)}
                        aria-label="Редагувати"
                      >
                        <Pencil aria-hidden="true" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>Редагувати</TooltipContent>
                  </Tooltip>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <Button
                        size="icon-sm"
                        variant="danger"
                        type="button"
                        disabled={rowDeleteState?.pending}
                        onClick={() => onDelete(item)}
                        aria-label="Видалити"
                      >
                        <Trash2 aria-hidden="true" />
                      </Button>
                    </TooltipTrigger>
                    <TooltipContent>
                      {rowDeleteState?.pending ? "Видаляємо…" : "Видалити"}
                    </TooltipContent>
                  </Tooltip>
                </div>
                {rowDeleteState?.error && (
                  <p className="field-error" role="alert">
                    {rowDeleteState.error}
                  </p>
                )}
              </TableCell>
            </TableRow>
          );
        })}

        {adding && (
          <AbbreviationRowForm
            dictionaryId={dictionaryId}
            editing={null}
            onDone={(saved) => {
              if (saved) onSaved(saved);
              setAdding(false);
            }}
          />
        )}
      </TableBody>
      <TableFooter>
        <TableRow>
          <TableCell colSpan={6} className="text-center">
            {!adding && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="fab"
                    variant="secondary"
                    type="button"
                    onClick={() => setAdding(true)}
                    aria-label="Додати скорочення"
                  >
                    <Plus aria-hidden="true" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Додати скорочення</TooltipContent>
              </Tooltip>
            )}
          </TableCell>
        </TableRow>
      </TableFooter>
    </Table>
  );
}
