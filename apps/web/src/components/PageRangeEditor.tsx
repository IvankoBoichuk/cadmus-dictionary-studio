import { usePageRangeEditor } from "../hooks/usePageRangeEditor";

/** BH-28: lets the user configure one or more physical PDF page ranges. */
export function PageRangeEditor({ dictionaryId }: { dictionaryId: string }) {
  const editor = usePageRangeEditor(dictionaryId);

  if (editor.state.status === "loading") {
    return <p role="status">Завантажуємо діапазони сторінок…</p>;
  }
  if (editor.state.status === "error") {
    return (
      <p className="form-error" role="alert">
        {editor.state.message}
      </p>
    );
  }

  return (
    <div className="form-section" aria-labelledby="page-ranges-heading">
      <h2 id="page-ranges-heading">Діапазони сторінок</h2>
      <p className="section-hint">
        {editor.pageCount === null
          ? "PDF ще не пройшов перевірку структури; діапазони можна буде вказати після її завершення."
          : `У файлі ${editor.pageCount} стор. Використовуються фізичні номери сторінок PDF, а не надруковані на них номери.`}
      </p>

      <ol className="page-range-list">
        {editor.rows.map((row, index) => (
          <li className="page-range-row" key={index}>
            <label className="visually-hidden" htmlFor={`range-start-${index}`}>
              Початкова сторінка
            </label>
            <input
              id={`range-start-${index}`}
              inputMode="numeric"
              value={row.start_page}
              onChange={(event) =>
                editor.updateRow(index, { ...row, start_page: event.target.value })
              }
              aria-invalid={Boolean(editor.errors[`ranges.${index}.start_page`])}
              aria-describedby={
                editor.errors[`ranges.${index}.start_page`]
                  ? `range-start-error-${index}`
                  : undefined
              }
            />
            <span aria-hidden="true">–</span>
            <label className="visually-hidden" htmlFor={`range-end-${index}`}>
              Кінцева сторінка
            </label>
            <input
              id={`range-end-${index}`}
              inputMode="numeric"
              value={row.end_page}
              onChange={(event) =>
                editor.updateRow(index, { ...row, end_page: event.target.value })
              }
              aria-invalid={Boolean(editor.errors[`ranges.${index}.end_page`])}
              aria-describedby={
                editor.errors[`ranges.${index}.end_page`]
                  ? `range-end-error-${index}`
                  : undefined
              }
            />
            <button
              type="button"
              className="icon-button"
              onClick={() => editor.removeRow(index)}
              aria-label={`Видалити діапазон ${index + 1}`}
            >
              ✕
            </button>
            {editor.errors[`ranges.${index}.start_page`] && (
              <p className="field-error" id={`range-start-error-${index}`}>
                {editor.errors[`ranges.${index}.start_page`]}
              </p>
            )}
            {editor.errors[`ranges.${index}.end_page`] && (
              <p className="field-error" id={`range-end-error-${index}`}>
                {editor.errors[`ranges.${index}.end_page`]}
              </p>
            )}
          </li>
        ))}
      </ol>

      <button type="button" className="secondary-button" onClick={editor.addRow}>
        Додати діапазон
      </button>

      <div className="form-actions">
        {editor.message && (
          <p className="result-message--success" role="status">
            {editor.message}
          </p>
        )}
        {editor.submissionError && (
          <p className="form-error" role="alert">
            {editor.submissionError}
          </p>
        )}
        <button
          disabled={editor.submitting}
          type="button"
          onClick={() => void editor.submit()}
        >
          {editor.submitting ? "Зберігаємо…" : "Зберегти діапазони"}
        </button>
      </div>
    </div>
  );
}
