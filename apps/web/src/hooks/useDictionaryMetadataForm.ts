import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import * as z from "zod";

import {
  API,
  fieldErrorsFrom,
  type ContributorRole,
  type DictionaryResponse,
  type LegalStatus,
} from "../api";
import { validateIsbn, validatePublicationYear } from "../dictionaryValidation";

export type ContributorFormValue = { name: string; role: ContributorRole };

const CONTRIBUTOR_ROLES = ["compiler", "author"] as const;

const metadataSchema = z
  .object({
    title: z.string(),
    description: z.string(),
    article_description: z.string(),
    dictionary_type: z.string(),
    publisher: z.string(),
    publication_year: z.string(),
    edition: z.string(),
    isbn: z.string(),
    digital_source: z.string(),
    legal_status: z.string(),
    license_type: z.string(),
    permission_reference: z.string(),
    rights_note: z.string(),
    contributors: z.array(
      z.object({ name: z.string(), role: z.enum(CONTRIBUTOR_ROLES) }),
    ),
    language_codes: z.array(z.string()),
  })
  .superRefine((values, ctx) => {
    if (values.publication_year.trim()) {
      const year = Number(values.publication_year);
      const yearError = Number.isNaN(year)
        ? "Рік видання має бути числом."
        : validatePublicationYear(year);
      if (yearError) {
        ctx.addIssue({
          code: "custom",
          path: ["publication_year"],
          message: yearError,
        });
      }
    }

    if (values.isbn.trim()) {
      const { error } = validateIsbn(values.isbn);
      if (error) {
        ctx.addIssue({ code: "custom", path: ["isbn"], message: error });
      }
    }

    if (values.legal_status === "licensed" && !values.license_type.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["license_type"],
        message: "Вкажіть тип ліцензії для статусу 'licensed'.",
      });
    }
    if (
      values.legal_status === "permission_granted" &&
      !values.permission_reference.trim()
    ) {
      ctx.addIssue({
        code: "custom",
        path: ["permission_reference"],
        message: "Вкажіть ідентифікатор чи опис дозволу.",
      });
    }
  });

export type MetadataFormValues = z.infer<typeof metadataSchema>;

function initialValuesFrom(dictionary: DictionaryResponse): MetadataFormValues {
  return {
    title: dictionary.title ?? "",
    description: dictionary.description ?? "",
    article_description: dictionary.article_description ?? "",
    dictionary_type: dictionary.dictionary_type ?? "",
    publisher: dictionary.publisher ?? "",
    publication_year:
      dictionary.publication_year === null
        ? ""
        : String(dictionary.publication_year),
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
  const [message, setMessage] = useState<string | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);

  const form = useForm<MetadataFormValues>({
    resolver: zodResolver(metadataSchema),
    defaultValues: initialValuesFrom(initialDictionary),
    mode: "onBlur",
  });
  const contributors = useFieldArray({
    control: form.control,
    name: "contributors",
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setMessage(null);
    setSubmissionError(null);
    try {
      const saved = await API.dictionaries.saveMetadata(dictionary.id, {
        title: values.title.trim() || null,
        description: values.description.trim() || null,
        article_description: values.article_description.trim() || null,
        dictionary_type: values.dictionary_type.trim() || null,
        publisher: values.publisher.trim() || null,
        publication_year: values.publication_year.trim()
          ? Number(values.publication_year)
          : null,
        edition: values.edition.trim() || null,
        isbn: values.isbn.trim() || null,
        digital_source: values.digital_source.trim() || null,
        legal_status: (values.legal_status || null) as LegalStatus | null,
        license_type: values.license_type.trim() || null,
        permission_reference: values.permission_reference.trim() || null,
        rights_note: values.rights_note.trim() || null,
        contributors: values.contributors,
        language_codes: values.language_codes,
      });
      setDictionary(saved);
      setMissingRequiredFields(saved.missing_required_fields);
      // reset (not setValue) so `isDirty` clears -- the unsaved-changes guard
      // keys off it.
      form.reset(initialValuesFrom(saved));
      setMessage(
        saved.missing_required_fields.length === 0
          ? "Чернетку збережено. Усі обов'язкові поля заповнено."
          : "Чернетку збережено. Деякі обов'язкові поля ще відсутні.",
      );
      onSaved?.(saved);
    } catch (error) {
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors) {
        for (const [field, fieldMessage] of Object.entries(apiErrors)) {
          form.setError(field as keyof MetadataFormValues, {
            message: fieldMessage,
          });
        }
        setSubmissionError("Перевірте поля, позначені помилками.");
        return;
      }
      setSubmissionError("Не вдалося зберегти метадані. Спробуйте ще раз.");
    }
  });

  const toggleLanguage = (code: string) => {
    const current = form.getValues("language_codes");
    form.setValue(
      "language_codes",
      current.includes(code)
        ? current.filter((value) => value !== code)
        : [...current, code],
      { shouldDirty: true },
    );
  };

  return {
    form,
    onSubmit,
    dictionary,
    missingRequiredFields,
    message,
    submissionError,
    contributorFields: contributors.fields,
    addContributor: (contributor: ContributorFormValue) =>
      contributors.append(contributor),
    removeContributor: (index: number) => contributors.remove(index),
    moveContributor: (index: number, direction: -1 | 1) =>
      contributors.move(index, index + direction),
    toggleLanguage,
  };
}
