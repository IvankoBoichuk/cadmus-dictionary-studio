import { useRef } from "react";

import type { SettlementMappingResponse } from "../api";
import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useSettlementForm } from "../hooks/useSettlementForm";
import { useUnsavedChangesWarning } from "../hooks/useUnsavedChangesWarning";
import { SettlementSearchCombobox } from "./SettlementSearchCombobox";

export function SettlementForm({
  dictionaryId,
  editing,
  onSaved,
  onCancel,
}: {
  dictionaryId: string;
  editing: SettlementMappingResponse | null;
  onSaved: (saved: SettlementMappingResponse) => void;
  onCancel?: () => void;
}) {
  const form = useSettlementForm(dictionaryId, editing, onSaved);
  const formRef = useRef<HTMLFormElement>(null);

  useFocusFirstError(formRef, form.submitCount, form.isSubmitting);
  useUnsavedChangesWarning(form.dirty && !form.isSubmitting);

  return (
    <form
      noValidate
      ref={formRef}
      onSubmit={form.submit}
      aria-labelledby="settlement-form-heading"
      className="form-section"
    >
      <h2 id="settlement-form-heading">
        {editing ? "Редагувати географічну мітку" : "Додати географічну мітку"}
      </h2>

      <div className="form-field">
        <label htmlFor="source_label">Позначка з оригіналу</label>
        <input
          id="source_label"
          {...form.getFieldProps("source_label")}
          aria-invalid={Boolean(form.errors.source_label)}
          aria-describedby={
            form.errors.source_label ? "source-label-error" : undefined
          }
        />
        {form.errors.source_label && (
          <p className="field-error" id="source-label-error">
            {form.errors.source_label}
          </p>
        )}
      </div>

      <div className="form-field">
        <label htmlFor="source_note">Примітка з оригіналу</label>
        <textarea id="source_note" rows={2} {...form.getFieldProps("source_note")} />
      </div>

      <fieldset className="form-field">
        <legend>Сучасна відповідність (AC8)</legend>
        {form.values.settlement_id ? (
          <p className="lede">
            Зіставлено з: {form.values.modern_settlement_name || "—"} (
            {form.values.settlement_category || "—"}).{" "}
            <button
              type="button"
              className="icon-button"
              onClick={form.clearSuggestion}
            >
              Скасувати зіставлення
            </button>
          </p>
        ) : (
          <SettlementSearchCombobox
            dictionaryId={dictionaryId}
            onSelect={form.applySuggestion}
          />
        )}
      </fieldset>

      <div className="form-field">
        <label htmlFor="modern_settlement_name">Сучасна назва (за потреби вручну)</label>
        <input
          id="modern_settlement_name"
          {...form.getFieldProps("modern_settlement_name")}
        />
      </div>

      <div className="form-field">
        <label htmlFor="settlement_category">Категорія (за потреби вручну)</label>
        <input
          id="settlement_category"
          {...form.getFieldProps("settlement_category")}
        />
      </div>

      {form.submissionError && (
        <p className="form-error" role="alert">
          {form.submissionError}
        </p>
      )}

      <div className="form-actions">
        <button disabled={form.submitting} type="submit">
          {form.submitting ? "Зберігаємо…" : editing ? "Зберегти зміни" : "Додати"}
        </button>
        {editing && onCancel && (
          <button type="button" className="secondary-button" onClick={onCancel}>
            Скасувати
          </button>
        )}
      </div>
    </form>
  );
}
