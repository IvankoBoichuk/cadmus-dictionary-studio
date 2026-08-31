import { useRef } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { AbbreviationResponse } from "../api";
import { useAbbreviationImport } from "../hooks/useAbbreviationImport";
import { CATEGORY_LABELS } from "../abbreviationCategories";

/**
 * BH-29 bulk import: upload a CSV or JSON file, review a row-by-row preview
 * (valid / duplicate / invalid), then confirm to persist only the valid rows
 * (AC5, AC6).
 */
export function AbbreviationImportPanel({
  dictionaryId,
  onImported,
}: {
  dictionaryId: string;
  onImported: (items: AbbreviationResponse[]) => void;
}) {
  const { state, preview, commit, reset } = useAbbreviationImport(
    dictionaryId,
    onImported,
  );
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) void preview(file);
  };

  const handleReset = () => {
    reset();
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <section className="form-section" aria-labelledby="import-heading">
      <h2 id="import-heading">Масовий імпорт</h2>
      <p className="section-hint">
        Завантажте CSV або JSON зі стовпцями/полями: abbreviation, full_form,
        category, language_code, variants (через «;» у CSV), note, unresolved.
        Перед імпортом можна переглянути валідні записи та помилки.
      </p>

      {(state.status === "idle" || state.status === "error") && (
        <div className="form-field">
          <Label htmlFor="import-file">Файл імпорту (.csv або .json)</Label>
          <Input
            id="import-file"
            ref={fileInputRef}
            type="file"
            accept=".csv,.json,text/csv,application/json"
            onChange={handleFileChange}
          />
        </div>
      )}

      {state.status === "previewing" && <p role="status">Аналізуємо файл…</p>}

      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}

      {(state.status === "previewed" || state.status === "committing") && (
        <>
          <p role="status">
            Валідних записів: {state.preview.valid_count} з {state.preview.rows.length}.
            {state.preview.error_count > 0 &&
              ` Записів з помилками або дублікатів: ${state.preview.error_count}.`}
          </p>
          <Table>
            <caption className="sr-only">Попередній перегляд імпорту</caption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">#</TableHead>
                <TableHead scope="col">Скорочення</TableHead>
                <TableHead scope="col">Категорія</TableHead>
                <TableHead scope="col">Статус</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {state.preview.rows.map((row) => (
                <TableRow key={row.row_number}>
                  <TableCell>{row.row_number}</TableCell>
                  <TableCell>{row.input?.abbreviation ?? "—"}</TableCell>
                  <TableCell>
                    {row.input ? CATEGORY_LABELS[row.input.category] : "—"}
                  </TableCell>
                  <TableCell>
                    {row.valid ? (
                      <Badge className="ml-2" variant="secondary">валідно</Badge>
                    ) : row.duplicate_of ? (
                      <Badge className="ml-2" variant="warning">дублікат у словнику</Badge>
                    ) : (
                      <Badge className="ml-2" variant="danger">
                        {Object.values(row.errors)[0] ?? "помилка"}
                      </Badge>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            </Table>
          <div className="form-actions">
            <Button
              type="button"
              disabled={state.status === "committing" || state.preview.valid_count === 0}
              onClick={() => void commit(state.preview)}
            >
              {state.status === "committing"
                ? "Імпортуємо…"
                : `Імпортувати ${state.preview.valid_count} записів`}
            </Button>
            <Button variant="secondary" type="button" onClick={handleReset}>
              Скасувати
            </Button>
          </div>
        </>
      )}

      {state.status === "done" && (
        <>
          <p className="m-0 text-[0.88rem] text-success-foreground" role="status">
            Імпортовано {state.outcome.imported.length} записів.
            {state.outcome.skipped.length > 0 &&
              ` Пропущено ${state.outcome.skipped.length} через помилки чи дублікати.`}
          </p>
          <Button variant="secondary" type="button" onClick={handleReset}>
            Імпортувати ще один файл
          </Button>
        </>
      )}
    </section>
  );
}
