import type { AbbreviationResponse } from "../api";
import { CATEGORY_OPTIONS } from "../abbreviationCategories";
import { useAbbreviationForm } from "../hooks/useAbbreviationForm";
import { LANGUAGE_OPTIONS } from "../languageOptions";

export function AbbreviationForm({
  dictionaryId,
  editing,
  onSaved,
  onCancel,
}: {
  dictionaryId: string;
  editing: AbbreviationResponse | null;
  onSaved: (saved: AbbreviationResponse) => void;
  onCancel?: () => void;
}) {
  const form = useAbbreviationForm(dictionaryId, editing, onSaved);

  return (
    <form
      noValidate
      onSubmit={form.submit}
      aria-labelledby="abbreviation-form-heading"
      className="form-section"
    >
      <h2 id="abbreviation-form-heading">
        {editing ? "Редагувати скорочення" : "Додати скорочення"}
      </h2>

      <div className="form-field">
        <label htmlFor="abbreviation">Скорочення</label>
        <input
          id="abbreviation"
          {...form.getFieldProps("abbreviation")}
          aria-invalid={Boolean(form.errors.abbreviation)}
          aria-describedby={
            form.errors.abbreviation ? "abbreviation-error" : undefined
          }
        />
        {form.errors.abbreviation && (
          <p className="field-error" id="abbreviation-error">
            {form.errors.abbreviation}
          </p>
        )}
      </div>

      <div className="form-field">
        <label htmlFor="category">Категорія</label>
        <select
          id="category"
          {...form.getFieldProps("category")}
          aria-invalid={Boolean(form.errors.category)}
          aria-describedby={form.errors.category ? "category-error" : undefined}
        >
          <option value="">Оберіть категорію</option>
          {CATEGORY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        {form.errors.category && (
          <p className="field-error" id="category-error">
            {form.errors.category}
          </p>
        )}
      </div>

      <div className="form-field">
        <label className="checkbox-field">
          <input
            type="checkbox"
            checked={form.values.unresolved}
            onChange={(event) =>
              void form.setFieldValue("unresolved", event.target.checked)
            }
          />
          Розшифрування поки невідоме (нерозшифрований запис)
        </label>
      </div>

      <div className="form-field">
        <label htmlFor="full_form">Повна форма</label>
        <input
          id="full_form"
          {...form.getFieldProps("full_form")}
          aria-invalid={Boolean(form.errors.full_form)}
          aria-describedby={form.errors.full_form ? "full-form-error" : undefined}
        />
        {form.errors.full_form && (
          <p className="field-error" id="full-form-error">
            {form.errors.full_form}
          </p>
        )}
      </div>

      <div className="form-field">
        <label htmlFor="language_code">Мова</label>
        <select id="language_code" {...form.getFieldProps("language_code")}>
          <option value="">Не вказано</option>
          {LANGUAGE_OPTIONS.map((language) => (
            <option key={language.code} value={language.code}>
              {language.name}
            </option>
          ))}
        </select>
      </div>

      <fieldset className="contributor-fieldset">
        <legend>Варіанти написання</legend>
        <ol className="contributor-list">
          {form.values.variants.map((variant, index) => (
            <li className="contributor-row" key={index}>
              <label className="visually-hidden" htmlFor={`variant-${index}`}>
                Варіант написання
              </label>
              <input
                id={`variant-${index}`}
                value={variant}
                onChange={(event) => form.updateVariant(index, event.target.value)}
              />
              <button
                type="button"
                className="icon-button"
                onClick={() => form.removeVariant(index)}
                aria-label={`Видалити варіант «${variant || "без назви"}»`}
              >
                ✕
              </button>
            </li>
          ))}
        </ol>
        <button type="button" className="secondary-button" onClick={form.addVariant}>
          Додати варіант написання
        </button>
      </fieldset>

      <div className="form-field">
        <label htmlFor="note">Примітка</label>
        <textarea id="note" rows={2} {...form.getFieldProps("note")} />
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
