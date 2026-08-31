import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import * as z from "zod";

import {
  API,
  duplicateAbbreviationFrom,
  fieldErrorsFrom,
  type AbbreviationCategory,
  type AbbreviationResponse,
} from "../api";

const abbreviationSchema = z
  .object({
    abbreviation: z.string(),
    category: z.string(),
    full_form: z.string(),
    language_code: z.string(),
    note: z.string(),
    unresolved: z.boolean(),
    variants: z.array(z.object({ value: z.string() })),
  })
  .superRefine((values, ctx) => {
    if (!values.abbreviation.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["abbreviation"],
        message: "Вкажіть скорочення.",
      });
    }
    if (!values.category) {
      ctx.addIssue({
        code: "custom",
        path: ["category"],
        message: "Оберіть категорію.",
      });
    }
    if (!values.unresolved && !values.full_form.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["full_form"],
        message:
          "Вкажіть повну форму. Якщо вона невідома, позначте запис як нерозшифрований.",
      });
    }
  });

export type AbbreviationFormValues = z.infer<typeof abbreviationSchema>;

const EMPTY_VALUES: AbbreviationFormValues = {
  abbreviation: "",
  category: "",
  full_form: "",
  language_code: "",
  note: "",
  unresolved: false,
  variants: [],
};

function valuesFrom(
  editing: AbbreviationResponse | null,
): AbbreviationFormValues {
  if (!editing) return EMPTY_VALUES;
  return {
    abbreviation: editing.abbreviation,
    category: editing.category,
    full_form: editing.full_form ?? "",
    language_code: editing.language_code ?? "",
    note: editing.note ?? "",
    unresolved: editing.unresolved,
    variants: editing.variants.map((value) => ({ value })),
  };
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
  const form = useForm<AbbreviationFormValues>({
    resolver: zodResolver(abbreviationSchema),
    defaultValues: valuesFrom(editing),
    mode: "onBlur",
  });
  const variants = useFieldArray({ control: form.control, name: "variants" });

  // `reset` clears field values, errors (including the form-level `root`), and
  // `isDirty` together -- so switching the row being edited also drops a stale
  // save error, the way Formik's `resetForm` used to.
  useEffect(() => {
    form.reset(valuesFrom(editing));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editing]);

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    const body = {
      abbreviation: values.abbreviation.trim(),
      category: values.category as AbbreviationCategory,
      full_form: values.unresolved
        ? values.full_form.trim() || null
        : values.full_form.trim(),
      language_code: values.language_code || null,
      note: values.note.trim() || null,
      unresolved: values.unresolved,
      variants: values.variants
        .map((variant) => variant.value.trim())
        .filter(Boolean),
    };
    try {
      const saved = editing
        ? await API.abbreviations.update(dictionaryId, editing.id, body)
        : await API.abbreviations.create(dictionaryId, body);
      onSaved(saved);
      if (!editing) form.reset(EMPTY_VALUES);
    } catch (error) {
      const duplicate = duplicateAbbreviationFrom(error);
      if (duplicate) {
        form.setError("root", { message: duplicate.message });
        return;
      }
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors) {
        for (const [field, message] of Object.entries(apiErrors)) {
          form.setError(field as keyof AbbreviationFormValues, { message });
        }
        form.setError("root", {
          message: "Перевірте поля, позначені помилками.",
        });
        return;
      }
      form.setError("root", {
        message: "Не вдалося зберегти скорочення. Спробуйте ще раз.",
      });
    }
  });

  return {
    form,
    onSubmit,
    variantFields: variants.fields,
    addVariant: () => variants.append({ value: "" }),
    removeVariant: (index: number) => variants.remove(index),
  };
}
