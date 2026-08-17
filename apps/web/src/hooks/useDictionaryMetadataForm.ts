import { useFormik } from "formik";
import { useState } from "react";

import {
  API,
  fieldErrorsFrom,
  type ContributorRole,
  type DictionaryResponse,
  type LegalStatus,
} from "../api";
import { validateIsbn, validatePublicationYear } from "../dictionaryValidation";

export type ContributorFormValue = { name: string; role: ContributorRole };

export type MetadataFormValues = {
  title: string;
  description: string;
  dictionary_type: string;
  publisher: string;
  publication_year: string;
  edition: string;
  isbn: string;
  digital_source: string;
  legal_status: LegalStatus | "";
  license_type: string;
  permission_reference: string;
  rights_note: string;
  contributors: ContributorFormValue[];
  language_codes: string[];
};

type FormErrors = Partial<Record<keyof MetadataFormValues, string>>;

function initialValuesFrom(dictionary: DictionaryResponse): MetadataFormValues {
  return {
    title: dictionary.title ?? "",
    description: dictionary.description ?? "",
    dictionary_type: dictionary.dictionary_type ?? "",
    publisher: dictionary.publisher ?? "",
    publication_year:
      dictionary.publication_year === null ? "" : String(dictionary.publication_year),
    edition: dictionary.edition ?? "",
    isbn: dictionary.isbn ?? "",
    digital_source: dictionary.digital_source ?? "",
    legal_status: dictionary.legal_status ?? "",
    license_type: dictionary.license_type ?? "",
    permission_reference: dictionary.permission_reference ?? "",
    rights_note: dictionary.rights_note ?? "",
    contributors: dictionary.contributors.map((contributor) => ({
      name: contributor.name,
      role: contributor.role,
    })),
    language_codes: [...dictionary.language_codes],
  };
}

function validate(values: MetadataFormValues): FormErrors {
  const errors: FormErrors = {};

  if (values.publication_year.trim()) {
    const year = Number(values.publication_year);
    const yearError = Number.isNaN(year)
      ? "Рік видання має бути числом."
      : validatePublicationYear(year);
    if (yearError) errors.publication_year = yearError;
  }

  if (values.isbn.trim()) {
    const { error } = validateIsbn(values.isbn);
    if (error) errors.isbn = error;
  }

  if (values.legal_status === "licensed" && !values.license_type.trim()) {
    errors.license_type = "Вкажіть тип ліцензії для статусу 'licensed'.";
  }
  if (
    values.legal_status === "permission_granted" &&
    !values.permission_reference.trim()
  ) {
    errors.permission_reference = "Вкажіть ідентифікатор чи опис дозволу.";
  }

  return errors;
}

/**
 * Drives BH-27's metadata step for one already-uploaded dictionary draft.
 * Saving never requires (or replaces) the uploaded PDF.
 */
export function useDictionaryMetadataForm(
  initialDictionary: DictionaryResponse,
  onSaved?: (dictionary: DictionaryResponse) => void,
) {
  const [dictionary, setDictionary] = useState(initialDictionary);
  const [missingRequiredFields, setMissingRequiredFields] = useState(
    initialDictionary.missing_required_fields,
  );

  const formik = useFormik<MetadataFormValues>({
    initialValues: initialValuesFrom(initialDictionary),
    validate,
    validateOnBlur: true,
    validateOnChange: false,
    onSubmit: async (values, helpers) => {
      helpers.setStatus(undefined);
      try {
        const saved = await API.dictionaries.saveMetadata(dictionary.id, {
          title: values.title.trim() || null,
          description: values.description.trim() || null,
          dictionary_type: values.dictionary_type.trim() || null,
          publisher: values.publisher.trim() || null,
          publication_year: values.publication_year.trim()
            ? Number(values.publication_year)
            : null,
          edition: values.edition.trim() || null,
          isbn: values.isbn.trim() || null,
          digital_source: values.digital_source.trim() || null,
          legal_status: values.legal_status || null,
          license_type: values.license_type.trim() || null,
          permission_reference: values.permission_reference.trim() || null,
          rights_note: values.rights_note.trim() || null,
          contributors: values.contributors,
          language_codes: values.language_codes,
        });
        setDictionary(saved);
        setMissingRequiredFields(saved.missing_required_fields);
        helpers.setValues(initialValuesFrom(saved));
        helpers.setStatus({
          message:
            saved.missing_required_fields.length === 0
              ? "Чернетку збережено. Усі обов'язкові поля заповнено."
              : "Чернетку збережено. Деякі обов'язкові поля ще відсутні.",
        });
        onSaved?.(saved);
      } catch (error) {
        const apiErrors = fieldErrorsFrom(error);
        if (apiErrors) {
          helpers.setErrors(apiErrors as FormErrors);
          helpers.setStatus({
            submissionError: "Перевірте поля, позначені помилками.",
          });
          return;
        }
        helpers.setStatus({
          submissionError: "Не вдалося зберегти метадані. Спробуйте ще раз.",
        });
      }
    },
  });

  const addContributor = (contributor: ContributorFormValue) => {
    void formik.setFieldValue("contributors", [
      ...formik.values.contributors,
      contributor,
    ]);
  };

  const updateContributor = (index: number, contributor: ContributorFormValue) => {
    const next = [...formik.values.contributors];
    next[index] = contributor;
    void formik.setFieldValue("contributors", next);
  };

  const removeContributor = (index: number) => {
    void formik.setFieldValue(
      "contributors",
      formik.values.contributors.filter((_, current) => current !== index),
    );
  };

  const moveContributor = (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    const current = formik.values.contributors[index];
    const target = formik.values.contributors[targetIndex];
    if (!current || !target) return;
    const next = [...formik.values.contributors];
    next[index] = target;
    next[targetIndex] = current;
    void formik.setFieldValue("contributors", next);
  };

  const toggleLanguage = (code: string) => {
    const selected = formik.values.language_codes.includes(code);
    void formik.setFieldValue(
      "language_codes",
      selected
        ? formik.values.language_codes.filter((current) => current !== code)
        : [...formik.values.language_codes, code],
    );
  };

  const status = formik.status as
    | { message?: string; submissionError?: string }
    | undefined;

  return {
    ...formik,
    dictionary,
    missingRequiredFields,
    message: status?.message ?? null,
    submissionError: status?.submissionError ?? null,
    submit: formik.handleSubmit,
    submitting: formik.isSubmitting,
    addContributor,
    updateContributor,
    removeContributor,
    moveContributor,
    toggleLanguage,
  } as const;
}
