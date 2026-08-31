import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { SettlementMappingResponse } from "../api";

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

export function SettlementsTable({
  mappings,
  onEdit,
  onDelete,
  onConfirm,
  onUnconfirm,
  deleteState,
}: {
  mappings: SettlementMappingResponse[];
  onEdit: (item: SettlementMappingResponse) => void;
  onDelete: (item: SettlementMappingResponse) => void;
  onConfirm: (item: SettlementMappingResponse) => void;
  onUnconfirm: (item: SettlementMappingResponse) => void;
  deleteState: Record<string, { pending: boolean; error: string | undefined } | undefined>;
}) {
  if (mappings.length === 0) {
    return <p className="lede">Географічних міток ще немає. Додайте першу нижче.</p>;
  }

  return (
    <Table>
      <caption className="sr-only">
        Список географічних міток словника
      </caption>
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
        {mappings.map((item) => {
          const rowDeleteState = deleteState[item.id];
          return (
            <TableRow key={item.id}>
              <TableCell>{item.source_label}</TableCell>
              <TableCell>{item.modern_settlement_name ?? "—"}</TableCell>
              <TableCell>{item.community_name ?? "—"}</TableCell>
              <TableCell>
                <Badge className="ml-2" variant={STATUS_BADGE_VARIANT[item.status]}>
                  {STATUS_LABELS[item.status]}
                </Badge>
              </TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    type="button"
                    onClick={() => onEdit(item)}
                  >
                    Редагувати
                  </Button>
                  {item.status === "suggested" && (
                    <Button
                      variant="secondary"
                      type="button"
                      onClick={() => onConfirm(item)}
                    >
                      Підтвердити
                    </Button>
                  )}
                  {item.status === "confirmed" && (
                    <Button
                      variant="secondary"
                      type="button"
                      onClick={() => onUnconfirm(item)}
                    >
                      Скасувати підтвердження
                    </Button>
                  )}
                  <Button
                    variant="danger"
                    type="button"
                    disabled={rowDeleteState?.pending}
                    onClick={() => onDelete(item)}
                  >
                    {rowDeleteState?.pending ? "Видаляємо…" : "Видалити"}
                  </Button>
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
      </TableBody>
      </Table>
  );
}
