import { Check, Pencil, Plus, Trash2, Undo2 } from "lucide-react";
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

import type { SettlementMappingResponse } from "../api";
import { SettlementRowForm } from "./SettlementRowForm";

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

const COMPACT =
  "text-[0.82rem] [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1 [&_td]:align-middle";

export function SettlementsTable({
  dictionaryId,
  mappings,
  onSaved,
  onDelete,
  onConfirm,
  onUnconfirm,
  deleteState,
}: {
  dictionaryId: string;
  mappings: SettlementMappingResponse[];
  onSaved: (item: SettlementMappingResponse) => void;
  onDelete: (item: SettlementMappingResponse) => void;
  onConfirm: (item: SettlementMappingResponse) => void;
  onUnconfirm: (item: SettlementMappingResponse) => void;
  deleteState: Record<
    string,
    { pending: boolean; error: string | undefined } | undefined
  >;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);

  return (
    <Table className={COMPACT}>
      <caption className="sr-only">Список географічних міток словника</caption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Позначка з оригіналу</TableHead>
          <TableHead scope="col">Сучасна відповідність</TableHead>
          <TableHead scope="col">Громада</TableHead>
          <TableHead scope="col">Статус</TableHead>
          <TableHead scope="col">Дії</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {mappings.length === 0 && !adding && (
          <TableRow>
            <TableCell colSpan={5} className="text-muted-foreground">
              Географічних міток ще немає. Натисніть + щоб додати першу.
            </TableCell>
          </TableRow>
        )}

        {mappings.map((item) => {
          const rowDeleteState = deleteState[item.id];
          if (editingId === item.id) {
            return (
              <SettlementRowForm
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
              <TableCell>{item.source_label}</TableCell>
              <TableCell>{item.modern_settlement_name ?? "—"}</TableCell>
              <TableCell>{item.community_name ?? "—"}</TableCell>
              <TableCell>
                <Badge variant={STATUS_BADGE_VARIANT[item.status]}>
                  {STATUS_LABELS[item.status]}
                </Badge>
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
                  {item.status === "suggested" && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon-sm"
                          variant="secondary"
                          type="button"
                          onClick={() => onConfirm(item)}
                          aria-label="Підтвердити"
                        >
                          <Check aria-hidden="true" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Підтвердити</TooltipContent>
                    </Tooltip>
                  )}
                  {item.status === "confirmed" && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          size="icon-sm"
                          variant="secondary"
                          type="button"
                          onClick={() => onUnconfirm(item)}
                          aria-label="Скасувати підтвердження"
                        >
                          <Undo2 aria-hidden="true" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>Скасувати підтвердження</TooltipContent>
                    </Tooltip>
                  )}
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
          <SettlementRowForm
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
          <TableCell colSpan={5} className="text-center">
            {!adding && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="fab"
                    variant="secondary"
                    type="button"
                    onClick={() => setAdding(true)}
                    aria-label="Додати географічну мітку"
                  >
                    <Plus aria-hidden="true" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Додати географічну мітку</TooltipContent>
              </Tooltip>
            )}
          </TableCell>
        </TableRow>
      </TableFooter>
    </Table>
  );
}
