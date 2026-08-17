import { useCallback, useEffect, useState } from "react";

import {
  API,
  apiMessageFrom,
  fieldErrorsFrom,
  isAbortError,
  type PageRange,
} from "../api";

export type PageRangeRow = { start_page: string; end_page: string };

export type PageRangeEditorLoadState =
  | { status: "loading" }
  | { status: "loaded" }
  | { status: "error"; message: string };

function rowsFrom(ranges: PageRange[]): PageRangeRow[] {
  return ranges.map((range) => ({
    start_page: String(range.start_page),
    end_page: String(range.end_page),
  }));
}

/** Drives BH-28's page-range editor: load, edit, validate, and save. */
export function usePageRangeEditor(dictionaryId: string) {
  const [state, setState] = useState<PageRangeEditorLoadState>({ status: "loading" });
  const [pageCount, setPageCount] = useState<number | null>(null);
  const [rows, setRows] = useState<PageRangeRow[]>([]);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    API.pageRanges.get(dictionaryId, { signal: controller.signal }).then(
      (response) => {
        setPageCount(response.page_count);
        setRows(rowsFrom(response.ranges));
        setState({ status: "loaded" });
      },
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ??
            "Не вдалося завантажити діапазони сторінок. Спробуйте пізніше.",
        });
      },
    );
    return () => controller.abort();
  }, [dictionaryId]);

  const addRow = useCallback(() => {
    setRows((current) => [...current, { start_page: "", end_page: "" }]);
  }, []);

  const updateRow = useCallback((index: number, row: PageRangeRow) => {
    setRows((current) => current.map((r, i) => (i === index ? row : r)));
  }, []);

  const removeRow = useCallback((index: number) => {
    setRows((current) => current.filter((_, i) => i !== index));
  }, []);

  const validate = useCallback((): Record<string, string> => {
    const validationErrors: Record<string, string> = {};
    rows.forEach((row, index) => {
      const start = Number(row.start_page);
      const end = Number(row.end_page);
      if (!row.start_page.trim() || Number.isNaN(start)) {
        validationErrors[`ranges.${index}.start_page`] =
          "Вкажіть початкову сторінку.";
      } else if (pageCount !== null && (start < 1 || start > pageCount)) {
        validationErrors[`ranges.${index}.start_page`] =
          `Початкова сторінка має бути в межах від 1 до ${pageCount}.`;
      }
      if (!row.end_page.trim() || Number.isNaN(end)) {
        validationErrors[`ranges.${index}.end_page`] = "Вкажіть кінцеву сторінку.";
      } else if (pageCount !== null && (end < 1 || end > pageCount)) {
        validationErrors[`ranges.${index}.end_page`] =
          `Кінцева сторінка має бути в межах від 1 до ${pageCount}.`;
      }
      if (
        !validationErrors[`ranges.${index}.start_page`] &&
        !validationErrors[`ranges.${index}.end_page`] &&
        start > end
      ) {
        validationErrors[`ranges.${index}.end_page`] =
          "Кінцева сторінка має бути не меншою за початкову.";
      }
    });
    return validationErrors;
  }, [rows, pageCount]);

  const submit = useCallback(async () => {
    setMessage(null);
    setSubmissionError(null);
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      setSubmissionError("Перевірте діапазони, позначені помилками.");
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      const saved = await API.pageRanges.save(dictionaryId, {
        ranges: rows.map((row) => ({
          start_page: Number(row.start_page),
          end_page: Number(row.end_page),
        })),
      });
      setRows(rowsFrom(saved.ranges));
      setMessage(
        saved.merged
          ? "Діапазони збережено. Деякі з них перетиналися й були об'єднані."
          : "Діапазони збережено.",
      );
    } catch (error) {
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors) {
        setErrors(apiErrors);
        setSubmissionError("Перевірте діапазони, позначені помилками.");
      } else {
        setSubmissionError(
          apiMessageFrom(error) ?? "Не вдалося зберегти діапазони. Спробуйте ще раз.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }, [dictionaryId, rows, validate]);

  return {
    state,
    pageCount,
    rows,
    errors,
    message,
    submissionError,
    submitting,
    addRow,
    updateRow,
    removeRow,
    submit,
  } as const;
}
