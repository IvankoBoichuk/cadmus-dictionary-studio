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
    <div className="table-wrapper">
      <table className="abbreviation-table">
        <caption className="visually-hidden">Список скорочень словника</caption>
        <thead>
          <tr>
            <th scope="col">Скорочення</th>
            <th scope="col">Повна форма</th>
            <th scope="col">Категорія</th>
            <th scope="col">Мова</th>
            <th scope="col">Варіанти</th>
            <th scope="col">Дії</th>
          </tr>
        </thead>
        <tbody>
          {abbreviations.map((item) => {
            const rowDeleteState = deleteState[item.id];
            return (
              <tr key={item.id}>
                <td>
                  {item.abbreviation}
                  {item.unresolved && (
                    <span className="badge badge--unresolved">нерозшифроване</span>
                  )}
                </td>
                <td>{item.full_form ?? "—"}</td>
                <td>{CATEGORY_LABELS[item.category]}</td>
                <td>{item.language_code ? LANGUAGE_NAMES[item.language_code] ?? item.language_code : "—"}</td>
                <td>{item.variants.length > 0 ? item.variants.join(", ") : "—"}</td>
                <td>
                  <div className="table-actions">
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onEdit(item)}
                    >
                      Редагувати
                    </button>
                    <button
                      type="button"
                      className="danger-button"
                      disabled={rowDeleteState?.pending}
                      onClick={() => onDelete(item)}
                    >
                      {rowDeleteState?.pending ? "Видаляємо…" : "Видалити"}
                    </button>
                  </div>
                  {rowDeleteState?.error && (
                    <p className="field-error" role="alert">
                      {rowDeleteState.error}
                    </p>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
