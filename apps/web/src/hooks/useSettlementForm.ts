import { useFormik } from "formik";
import { useEffect } from "react";

import {
  API,
  duplicateSettlementMappingFrom,
  fieldErrorsFrom,
  type SettlementMappingResponse,
  type SettlementSuggestionResponse,
} from "../api";

export type SettlementFormValues = {
  source_label: string;
  source_note: string;
  modern_settlement_name: string;
  settlement_category: string;
  settlement_id: string | null;
};

type FormErrors = Partial<Record<keyof SettlementFormValues, string>>;

const EMPTY_VALUES: SettlementFormValues = {
  source_label: "",
  source_note: "",
  modern_settlement_name: "",
  settlement_category: "",
  settlement_id: null,
};

function valuesFrom(
  editing: SettlementMappingResponse | null,
): SettlementFormValues {
  if (!editing) return EMPTY_VALUES;
  return {
    source_label: editing.source_label,
    source_note: editing.source_note ?? "",
    modern_settlement_name: editing.modern_settlement_name ?? "",
    settlement_category: editing.settlement_category ?? "",
    settlement_id: editing.settlement_id,
  };
}

function validate(values: SettlementFormValues): FormErrors {
  const errors: FormErrors = {};
  if (!values.source_label.trim()) {
    errors.source_label = "Вкажіть географічну позначку з оригіналу.";
  }
  return errors;
}

/**
 * Drives BH-30's single-mapping add/edit form (AC7, AC11, AC12).
 *
 * `editing` selects create vs. update; `onSaved` is called with the
 * persisted record so the caller can merge it into its own list state.
 * There is deliberately no way to submit `status="confirmed"` here (AC9)
 * -- picking a search suggestion only links `settlement_id`, which the
 * server turns into `status="suggested"`; confirming is a separate action.
 */
export function useSettlementForm(
  dictionaryId: string,
  editing: SettlementMappingResponse | null,
  onSaved: (saved: SettlementMappingResponse) => void,
) {
  const formik = useFormik<SettlementFormValues>({
    initialValues: valuesFrom(editing),
    validate,
    validateOnBlur: true,
    validateOnChange: false,
    onSubmit: async (values, helpers) => {
      helpers.setStatus(undefined);
      const body = {
        source_label: values.source_label.trim(),
        source_note: values.source_note.trim() || null,
        modern_settlement_name: values.modern_settlement_name.trim() || null,
        settlement_category: values.settlement_category.trim() || null,
        settlement_id: values.settlement_id,
      };
      try {
        const saved = editing
          ? await API.settlements.update(dictionaryId, editing.id, body)
          : await API.settlements.create(dictionaryId, body);
        onSaved(saved);
        if (!editing) helpers.resetForm();
      } catch (error) {
        const duplicate = duplicateSettlementMappingFrom(error);
        if (duplicate) {
          helpers.setStatus({ submissionError: duplicate.message });
          return;
        }
        const apiErrors = fieldErrorsFrom(error);
        if (apiErrors) {
          helpers.setErrors(apiErrors as FormErrors);
          helpers.setStatus({
            submissionError: "Перевірте поля, позначені помилками.",
          });
          return;
        }
        helpers.setStatus({
          submissionError: "Не вдалося зберегти географічну мітку. Спробуйте ще раз.",
        });
      }
    },
  });

  useEffect(() => {
    formik.resetForm({ values: valuesFrom(editing) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing]);

  const applySuggestion = (suggestion: SettlementSuggestionResponse) => {
    void formik.setFieldValue("settlement_id", suggestion.settlement_id);
    void formik.setFieldValue("modern_settlement_name", suggestion.title);
    void formik.setFieldValue("settlement_category", suggestion.category);
  };

  const clearSuggestion = () => {
    void formik.setFieldValue("settlement_id", null);
  };

  const status = formik.status as { submissionError?: string } | undefined;

  return {
    ...formik,
    submit: formik.handleSubmit,
    submitting: formik.isSubmitting,
    submissionError: status?.submissionError ?? null,
    applySuggestion,
    clearSuggestion,
  } as const;
}
