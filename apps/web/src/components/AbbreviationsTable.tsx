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

import type { AbbreviationResponse } from "../api";
import { LANGUAGE_OPTIONS } from "../languageOptions";
import { CATEGORY_LABELS } from "../abbreviationCategories";

const LANGUAGE_NAMES: Record<string, string> = Object.fromEntries(
  LANGUAGE_OPTIONS.map((language) => [language.code, language.name]),
);

export function AbbreviationsTable({
  abbreviations,
  onEdit,
  onDelete,
  deleteState,
}: {
  abbreviations: AbbreviationResponse[];
  onEdit: (item: AbbreviationResponse) => void;
  onDelete: (item: AbbreviationResponse) => void;
  deleteState: Record<string, { pending: boolean; error: string | undefined } | undefined>;
}) {
  if (abbreviations.length === 0) {
    return <p className="lede">Скорочень ще немає. Додайте перше нижче.</p>;
  }

  return (
    <Table>
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
        {abbreviations.map((item) => {
          const rowDeleteState = deleteState[item.id];
          return (
            <TableRow key={item.id}>
              <TableCell>
                {item.abbreviation}
                {item.unresolved && (
                  <Badge className="ml-2" variant="warning">нерозшифроване</Badge>
                )}
              </TableCell>
              <TableCell>{item.full_form ?? "—"}</TableCell>
              <TableCell>{CATEGORY_LABELS[item.category]}</TableCell>
              <TableCell>{item.language_code ? LANGUAGE_NAMES[item.language_code] ?? item.language_code : "—"}</TableCell>
              <TableCell>{item.variants.length > 0 ? item.variants.join(", ") : "—"}</TableCell>
              <TableCell>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    type="button"
                    onClick={() => onEdit(item)}
                  >
                    Редагувати
                  </Button>
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
