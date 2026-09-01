import { CirclePlus, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

import { usePageRangeEditor } from "../hooks/usePageRangeEditor";

/** BH-28: lets the user configure one or more physical PDF page ranges. */
export function PageRangeEditor({
  dictionaryId,
  portalActionsInto,
}: {
  dictionaryId: string;
  /** id of an element to portal the Save action into (the shared
   * `DictionaryLayout` sticky header) instead of rendering it inline. */
  portalActionsInto?: string;
}) {
  const editor = usePageRangeEditor(dictionaryId);

  // Resolve the sticky-header portal target once after mount, mirroring
  // `DictionaryMetadataForm`.
  const [portalNode, setPortalNode] = useState<HTMLElement | null>(null);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot DOM sync
    setPortalNode(
      portalActionsInto ? document.getElementById(portalActionsInto) : null,
    );
  }, [portalActionsInto]);

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

  const saveButton = (
    <Button form="page-ranges-form" disabled={editor.submitting} type="submit">
      {editor.submitting ? "Зберігаємо…" : "Зберегти діапазони"}
    </Button>
  );

  return (
    <form
      noValidate
      id="page-ranges-form"
      className="form-section"
      aria-labelledby="page-ranges-heading"
      onSubmit={handleSubmit}
    >
      {portalActionsInto
        ? portalNode && createPortal(saveButton, portalNode)
        : null}
      <h2 id="page-ranges-heading">Діапазони сторінок</h2>
      <p className="section-hint">
        {editor.pageCount === null
          ? "PDF ще не пройшов перевірку структури; діапазони можна буде вказати після її завершення."
          : `У файлі ${editor.pageCount} стор. Використовуються фізичні номери сторінок PDF, а не надруковані на них номери.`}
      </p>

      <ol className="my-3 grid max-w-md list-none gap-[0.6rem] p-0">
        {editor.rows.map((row, index) => (
          <li
            className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_auto] items-center gap-2"
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
            <span aria-hidden="true" className="text-center text-muted-foreground">
              –
            </span>
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
              <X aria-hidden="true" />
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
        <CirclePlus aria-hidden="true" />
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
        {!portalActionsInto && saveButton}
      </div>
    </form>
  );
}
