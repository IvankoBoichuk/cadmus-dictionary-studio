import { useFormik } from "formik";
import { useEffect } from "react";

import {
  API,
  duplicateAbbreviationFrom,
  fieldErrorsFrom,
  type AbbreviationCategory,
  type AbbreviationResponse,
} from "../api";

export type AbbreviationFormValues = {
  abbreviation: string;
  category: AbbreviationCategory | "";
  full_form: string;
  language_code: string;
  note: string;
  unresolved: boolean;
  variants: string[];
};

type FormErrors = Partial<Record<keyof AbbreviationFormValues, string>>;

const EMPTY_VALUES: AbbreviationFormValues = {
  abbreviation: "",
  category: "",
  full_form: "",
  language_code: "",
  note: "",
  unresolved: false,
  variants: [],
};

function valuesFrom(editing: AbbreviationResponse | null): AbbreviationFormValues {
  if (!editing) return EMPTY_VALUES;
  return {
    abbreviation: editing.abbreviation,
    category: editing.category,
    full_form: editing.full_form ?? "",
    language_code: editing.language_code ?? "",
    note: editing.note ?? "",
    unresolved: editing.unresolved,
    variants: [...editing.variants],
  };
}

function validate(values: AbbreviationFormValues): FormErrors {
  const errors: FormErrors = {};
  if (!values.abbreviation.trim()) errors.abbreviation = "Вкажіть скорочення.";
  if (!values.category) errors.category = "Оберіть категорію.";
  if (!values.unresolved && !values.full_form.trim()) {
    errors.full_form =
      "Вкажіть повну форму. Якщо вона невідома, позначте запис як нерозшифрований.";
  }
  return errors;
}

/**
 * Drives BH-29's single-abbreviation add/edit form (AC1-AC3).
 *
 * `editing` selects create vs. update; `onSaved` is called with the
 * persisted record so the caller can merge it into its own list state.
 */
export function useAbbreviationForm(
  dictionaryId: string,
  editing: AbbreviationResponse | null,
  onSaved: (saved: AbbreviationResponse) => void,
) {
  const formik = useFormik<AbbreviationFormValues>({
    initialValues: valuesFrom(editing),
    validate,
    validateOnBlur: true,
    validateOnChange: false,
    onSubmit: async (values, helpers) => {
      helpers.setStatus(undefined);
      const body = {
        abbreviation: values.abbreviation.trim(),
        category: values.category as AbbreviationCategory,
        full_form: values.unresolved ? values.full_form.trim() || null : values.full_form.trim(),
        language_code: values.language_code || null,
        note: values.note.trim() || null,
        unresolved: values.unresolved,
        variants: values.variants.map((variant) => variant.trim()).filter(Boolean),
      };
      try {
        const saved = editing
          ? await API.abbreviations.update(dictionaryId, editing.id, body)
          : await API.abbreviations.create(dictionaryId, body);
        onSaved(saved);
        if (!editing) helpers.resetForm();
      } catch (error) {
        const duplicate = duplicateAbbreviationFrom(error);
        if (duplicate) {
          helpers.setStatus({ submissionError: duplicate.message });
          return;
        }
        const apiErrors = fieldErrorsFrom(error);
        if (apiErrors) {
          helpers.setErrors(apiErrors as FormErrors);
          helpers.setStatus({ submissionError: "Перевірте поля, позначені помилками." });
          return;
        }
        helpers.setStatus({
          submissionError: "Не вдалося зберегти скорочення. Спробуйте ще раз.",
        });
      }
    },
  });

  useEffect(() => {
    formik.resetForm({ values: valuesFrom(editing) });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing]);

  const addVariant = () => {
    void formik.setFieldValue("variants", [...formik.values.variants, ""]);
  };

  const updateVariant = (index: number, value: string) => {
    const next = [...formik.values.variants];
    next[index] = value;
    void formik.setFieldValue("variants", next);
  };

  const removeVariant = (index: number) => {
    void formik.setFieldValue(
      "variants",
      formik.values.variants.filter((_, current) => current !== index),
    );
  };

  const status = formik.status as { submissionError?: string } | undefined;

  return {
    ...formik,
    submit: formik.handleSubmit,
    submitting: formik.isSubmitting,
    submissionError: status?.submissionError ?? null,
    addVariant,
    updateVariant,
    removeVariant,
  } as const;
}
