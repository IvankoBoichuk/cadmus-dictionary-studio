import { useRef } from "react";

import type { SettlementMappingResponse } from "../api";
import { useSettlementImport } from "../hooks/useSettlementImport";

/**
 * BH-30 bulk import: upload a CSV or JSON file, review a row-by-row preview
 * (valid / duplicate / invalid), then confirm to persist only the valid
 * rows. Every imported row starts as `status="unresolved"` -- matching a
 * modern settlement happens afterward, one row at a time.
 */
export function SettlementImportPanel({
  dictionaryId,
  onImported,
}: {
  dictionaryId: string;
  onImported: (items: SettlementMappingResponse[]) => void;
}) {
  const { state, preview, commit, reset } = useSettlementImport(
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
    <section className="form-section" aria-labelledby="settlement-import-heading">
      <h2 id="settlement-import-heading">Масовий імпорт</h2>
      <p className="section-hint">
        Завантажте CSV або JSON зі стовпцями/полями: source_label, source_note,
        modern_settlement_name, settlement_category. Перед імпортом можна
        переглянути валідні записи та помилки.
      </p>

      {(state.status === "idle" || state.status === "error") && (
        <div className="form-field">
          <label htmlFor="settlement-import-file">Файл імпорту (.csv або .json)</label>
          <input
            id="settlement-import-file"
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
          <div className="table-wrapper">
            <table className="settlement-table">
              <caption className="visually-hidden">Попередній перегляд імпорту</caption>
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Позначка з оригіналу</th>
                  <th scope="col">Статус</th>
                </tr>
              </thead>
              <tbody>
                {state.preview.rows.map((row) => (
                  <tr key={row.row_number}>
                    <td>{row.row_number}</td>
                    <td>{row.input?.source_label ?? "—"}</td>
                    <td>
                      {row.valid ? (
                        <span className="badge badge--ok">валідно</span>
                      ) : row.duplicate_of ? (
                        <span className="badge badge--warning">дублікат у словнику</span>
                      ) : (
                        <span className="badge badge--error">
                          {Object.values(row.errors)[0] ?? "помилка"}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="form-actions">
            <button
              type="button"
              disabled={state.status === "committing" || state.preview.valid_count === 0}
              onClick={() => void commit(state.preview)}
            >
              {state.status === "committing"
                ? "Імпортуємо…"
                : `Імпортувати ${state.preview.valid_count} записів`}
            </button>
            <button type="button" className="secondary-button" onClick={handleReset}>
              Скасувати
            </button>
          </div>
        </>
      )}

      {state.status === "done" && (
        <>
          <p className="result-message--success" role="status">
            Імпортовано {state.outcome.imported.length} записів.
            {state.outcome.skipped.length > 0 &&
              ` Пропущено ${state.outcome.skipped.length} через помилки чи дублікати.`}
          </p>
          <button type="button" className="secondary-button" onClick={handleReset}>
            Імпортувати ще один файл
          </button>
        </>
      )}
    </section>
  );
}
