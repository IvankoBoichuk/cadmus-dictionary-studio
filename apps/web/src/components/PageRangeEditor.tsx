import { type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { usePageRangeEditor } from "../hooks/usePageRangeEditor";

/** BH-28: lets the user configure one or more physical PDF page ranges. */
export function PageRangeEditor({ dictionaryId }: { dictionaryId: string }) {
  const editor = usePageRangeEditor(dictionaryId);

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    void editor.submit();
  };

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
    <form
      noValidate
      className="form-section"
      aria-labelledby="page-ranges-heading"
      onSubmit={handleSubmit}
    >
      <h2 id="page-ranges-heading">Діапазони сторінок</h2>
      <p className="section-hint">
        {editor.pageCount === null
          ? "PDF ще не пройшов перевірку структури; діапазони можна буде вказати після її завершення."
          : `У файлі ${editor.pageCount} стор. Використовуються фізичні номери сторінок PDF, а не надруковані на них номери.`}
      </p>

      <ol className="my-3 grid list-none gap-[0.6rem] p-0">
        {editor.rows.map((row, index) => (
          <li
            className="grid grid-cols-[6rem_auto_6rem_auto] items-center gap-2"
            key={index}
          >
            <label className="sr-only" htmlFor={`range-start-${index}`}>
              Початкова сторінка
            </label>
            <Input
              className="min-h-[2.6rem] px-[0.65rem] py-2"
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
            <label className="sr-only" htmlFor={`range-end-${index}`}>
              Кінцева сторінка
            </label>
            <Input
              className="min-h-[2.6rem] px-[0.65rem] py-2"
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
            <Button
              variant="secondary"
              size="icon"
              type="button"
              onClick={() => editor.removeRow(index)}
              aria-label={`Видалити діапазон ${index + 1}`}
            >
              ✕
            </Button>
            {editor.errors[`ranges.${index}.start_page`] && (
              <p className="field-error col-span-full" id={`range-start-error-${index}`}>
                {editor.errors[`ranges.${index}.start_page`]}
              </p>
            )}
            {editor.errors[`ranges.${index}.end_page`] && (
              <p className="field-error col-span-full" id={`range-end-error-${index}`}>
                {editor.errors[`ranges.${index}.end_page`]}
              </p>
            )}
          </li>
        ))}
      </ol>

      <Button variant="secondary" type="button" onClick={editor.addRow}>
        Додати діапазон
      </Button>

      <div className="form-actions">
        {editor.message && (
          <p className="m-0 text-[0.88rem] text-success-foreground" role="status">
            {editor.message}
          </p>
        )}
        {editor.submissionError && (
          <p className="form-error" role="alert">
            {editor.submissionError}
          </p>
        )}
        <Button disabled={editor.submitting} type="submit">
          {editor.submitting ? "Зберігаємо…" : "Зберегти діапазони"}
        </Button>
      </div>
    </form>
  );
}
