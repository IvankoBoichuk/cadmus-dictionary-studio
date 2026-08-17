import { useEffect, useRef } from "react";

import type { ContributorRole, DictionaryResponse, LegalStatus } from "../api";
import { useDictionaryMetadataForm } from "../hooks/useDictionaryMetadataForm";
import { LANGUAGE_OPTIONS } from "../languageOptions";

const MISSING_FIELD_LABELS: Record<string, string> = {
  title: "Назва",
  languages: "Мови",
  legal_status: "Правовий статус",
};

const LEGAL_STATUS_OPTIONS: { value: LegalStatus; label: string }[] = [
  { value: "public_domain", label: "Суспільне надбання" },
  { value: "licensed", label: "За ліцензією" },
  { value: "permission_granted", label: "Дозвіл отримано" },
  { value: "restricted", label: "Обмежений доступ" },
  { value: "unknown", label: "Невідомо" },
];

const CONTRIBUTOR_ROLE_OPTIONS: { value: ContributorRole; label: string }[] = [
  { value: "compiler", label: "Укладач(ка)" },
  { value: "author", label: "Автор(ка)" },
];

export function DictionaryMetadataForm({
  initialDictionary,
  source,
  onSaved,
}: {
  initialDictionary: DictionaryResponse;
  source?: DictionaryResponse["source"];
  onSaved?: (dictionary: DictionaryResponse) => void;
}) {
  const form = useDictionaryMetadataForm(initialDictionary, onSaved);
  const formRef = useRef<HTMLFormElement>(null);

  useEffect(() => {
    if (form.submitCount === 0 || form.isSubmitting) return;
    const invalidField = formRef.current?.querySelector<HTMLElement>(
      '[aria-invalid="true"]',
    );
    invalidField?.focus();
  }, [form.submitCount, form.isSubmitting]);

  return (
    <form
      noValidate
      ref={formRef}
      onSubmit={form.submit}
      aria-labelledby="metadata-heading"
    >
      {source && (
        <div className="form-section">
          <h2 id="metadata-heading">Джерело</h2>
          <p className="file-summary">
            {source.original_filename} · {(source.byte_size / 1024).toFixed(0)} КБ
            {source.inspection_status === "pending" && " · перевіряємо PDF…"}
            {source.inspection_status === "verified" &&
              source.page_count !== null &&
              ` · ${source.page_count} стор.`}
            {source.inspection_status === "failed" &&
              " · PDF не пройшов перевірку структури."}
          </p>
        </div>
      )}

      <div className="form-section" aria-labelledby="bibliographic-heading">
        <h2 id="bibliographic-heading">2. Бібліографічні дані</h2>

        <div className="form-field">
          <label htmlFor="title">Назва</label>
          <input
            id="title"
            {...form.getFieldProps("title")}
            aria-invalid={Boolean(form.errors.title)}
            aria-describedby={form.errors.title ? "title-error" : undefined}
          />
          {form.errors.title && (
            <p className="field-error" id="title-error">
              {form.errors.title}
            </p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="description">Опис</label>
          <textarea id="description" rows={3} {...form.getFieldProps("description")} />
        </div>

        <div className="form-field">
          <label htmlFor="dictionary_type">Тип словника</label>
          <input id="dictionary_type" {...form.getFieldProps("dictionary_type")} />
        </div>

        <div className="form-field">
          <label htmlFor="publisher">Видавництво</label>
          <input id="publisher" {...form.getFieldProps("publisher")} />
        </div>

        <div className="form-field">
          <label htmlFor="publication_year">Рік видання</label>
          <input
            id="publication_year"
            inputMode="numeric"
            {...form.getFieldProps("publication_year")}
            aria-invalid={Boolean(form.errors.publication_year)}
            aria-describedby={
              form.errors.publication_year ? "publication-year-error" : undefined
            }
          />
          {form.errors.publication_year && (
            <p className="field-error" id="publication-year-error">
              {form.errors.publication_year}
            </p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="edition">Видання (номер / назва)</label>
          <input id="edition" {...form.getFieldProps("edition")} />
        </div>

        <div className="form-field">
          <label htmlFor="isbn">ISBN</label>
          <input
            id="isbn"
            {...form.getFieldProps("isbn")}
            aria-invalid={Boolean(form.errors.isbn)}
            aria-describedby={form.errors.isbn ? "isbn-error" : undefined}
          />
          {form.errors.isbn && (
            <p className="field-error" id="isbn-error">
              {form.errors.isbn}
            </p>
          )}
        </div>

        <div className="form-field">
          <label htmlFor="digital_source">Джерело цифрової копії</label>
          <input id="digital_source" {...form.getFieldProps("digital_source")} />
        </div>

        <fieldset className="contributor-fieldset">
          <legend>Автори та укладачі</legend>
          <ol className="contributor-list">
            {form.values.contributors.map((contributor, index) => (
              <li className="contributor-row" key={index}>
                <label className="visually-hidden" htmlFor={`contributor-name-${index}`}>
                  Ім'я
                </label>
                <input
                  id={`contributor-name-${index}`}
                  value={contributor.name}
                  onChange={(event) =>
                    form.updateContributor(index, {
                      ...contributor,
                      name: event.target.value,
                    })
                  }
                />
                <label
                  className="visually-hidden"
                  htmlFor={`contributor-role-${index}`}
                >
                  Роль
                </label>
                <select
                  id={`contributor-role-${index}`}
                  value={contributor.role}
                  onChange={(event) =>
                    form.updateContributor(index, {
                      ...contributor,
                      role: event.target.value as ContributorRole,
                    })
                  }
                >
                  {CONTRIBUTOR_ROLE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => form.moveContributor(index, -1)}
                  disabled={index === 0}
                  aria-label={`Перемістити ${contributor.name || "запис"} вище`}
                >
                  ↑
                </button>
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => form.moveContributor(index, 1)}
                  disabled={index === form.values.contributors.length - 1}
                  aria-label={`Перемістити ${contributor.name || "запис"} нижче`}
                >
                  ↓
                </button>
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => form.removeContributor(index)}
                  aria-label={`Видалити ${contributor.name || "запис"}`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ol>
          <button
            type="button"
            className="secondary-button"
            onClick={() => form.addContributor({ name: "", role: "compiler" })}
          >
            Додати автора чи укладача
          </button>
        </fieldset>
      </div>

      <div className="form-section" aria-labelledby="languages-heading">
        <h2 id="languages-heading">3. Мови</h2>
        <p className="section-hint">Оберіть одну чи декілька мов словника.</p>
        <div className="language-grid" role="group" aria-labelledby="languages-heading">
          {LANGUAGE_OPTIONS.map((language) => (
            <label className="language-option" key={language.code}>
              <input
                type="checkbox"
                checked={form.values.language_codes.includes(language.code)}
                onChange={() => form.toggleLanguage(language.code)}
              />
              {language.name}
            </label>
          ))}
        </div>
        {form.errors.language_codes && (
          <p className="field-error" role="alert">
            {form.errors.language_codes}
          </p>
        )}
      </div>

      <div className="form-section" aria-labelledby="legal-heading">
        <h2 id="legal-heading">4. Правовий статус</h2>

        <div className="form-field">
          <label htmlFor="legal_status">Правовий статус</label>
          <select id="legal_status" {...form.getFieldProps("legal_status")}>
            <option value="">Не вказано</option>
            {LEGAL_STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {form.values.legal_status === "licensed" && (
          <div className="form-field">
            <label htmlFor="license_type">Тип ліцензії</label>
            <input
              id="license_type"
              {...form.getFieldProps("license_type")}
              aria-invalid={Boolean(form.errors.license_type)}
              aria-describedby={
                form.errors.license_type ? "license-type-error" : undefined
              }
            />
            {form.errors.license_type && (
              <p className="field-error" id="license-type-error">
                {form.errors.license_type}
              </p>
            )}
          </div>
        )}

        {form.values.legal_status === "permission_granted" && (
          <div className="form-field">
            <label htmlFor="permission_reference">Ідентифікатор чи опис дозволу</label>
            <input
              id="permission_reference"
              {...form.getFieldProps("permission_reference")}
              aria-invalid={Boolean(form.errors.permission_reference)}
              aria-describedby={
                form.errors.permission_reference
                  ? "permission-reference-error"
                  : undefined
              }
            />
            {form.errors.permission_reference && (
              <p className="field-error" id="permission-reference-error">
                {form.errors.permission_reference}
              </p>
            )}
          </div>
        )}

        <div className="form-field">
          <label htmlFor="rights_note">Примітка щодо прав</label>
          <textarea id="rights_note" rows={2} {...form.getFieldProps("rights_note")} />
        </div>
      </div>

      <div className="form-section" aria-labelledby="save-heading">
        <h2 id="save-heading">5. Збереження чернетки</h2>
        {form.missingRequiredFields.length > 0 && (
          <p className="missing-fields" role="status">
            {"Ще не заповнено: " +
              form.missingRequiredFields
                .map((field) => MISSING_FIELD_LABELS[field] ?? field)
                .join(", ") +
              ". Чернетку можна зберегти й заповнити пізніше."}
          </p>
        )}
        {form.message && (
          <p className="result-message--success" role="status">
            {form.message}
          </p>
        )}
        {form.submissionError && (
          <p className="form-error" role="alert">
            {form.submissionError}
          </p>
        )}
        <button disabled={form.submitting} type="submit">
          {form.submitting ? "Зберігаємо…" : "Зберегти чернетку"}
        </button>
      </div>
    </form>
  );
}
