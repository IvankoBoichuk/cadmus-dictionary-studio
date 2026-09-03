import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";

import {
  API,
  duplicateSettlementMappingFrom,
  fieldErrorsFrom,
  type SettlementMappingResponse,
  type SettlementSuggestionResponse,
} from "../api";

const settlementSchema = z
  .object({
    source_label: z.string(),
    source_note: z.string(),
    district: z.string(),
    modern_settlement_name: z.string(),
    settlement_category: z.string(),
    settlement_id: z.string().nullable(),
  })
  .superRefine((values, ctx) => {
    if (!values.source_label.trim()) {
      ctx.addIssue({
        code: "custom",
        path: ["source_label"],
        message: "Вкажіть географічну позначку з оригіналу.",
      });
    }
  });

export type SettlementFormValues = z.infer<typeof settlementSchema>;

const EMPTY_VALUES: SettlementFormValues = {
  source_label: "",
  source_note: "",
  district: "",
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
    district: editing.district ?? "",
    modern_settlement_name: editing.modern_settlement_name ?? "",
    settlement_category: editing.settlement_category ?? "",
    settlement_id: editing.settlement_id,
  };
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
  const form = useForm<SettlementFormValues>({
    resolver: zodResolver(settlementSchema),
    defaultValues: valuesFrom(editing),
    mode: "onBlur",
  });

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
      source_label: values.source_label.trim(),
      source_note: values.source_note.trim() || null,
      district: values.district.trim() || null,
      modern_settlement_name: values.modern_settlement_name.trim() || null,
      settlement_category: values.settlement_category.trim() || null,
      settlement_id: values.settlement_id,
    };
    try {
      const saved = editing
        ? await API.settlements.update(dictionaryId, editing.id, body)
        : await API.settlements.create(dictionaryId, body);
      onSaved(saved);
      if (!editing) form.reset(EMPTY_VALUES);
    } catch (error) {
      const duplicate = duplicateSettlementMappingFrom(error);
      if (duplicate) {
        form.setError("root", { message: duplicate.message });
        return;
      }
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors) {
        for (const [field, message] of Object.entries(apiErrors)) {
          form.setError(field as keyof SettlementFormValues, { message });
        }
        form.setError("root", {
          message: "Перевірте поля, позначені помилками.",
        });
        return;
      }
      form.setError("root", {
        message: "Не вдалося зберегти географічну мітку. Спробуйте ще раз.",
      });
    }
  });

  const applySuggestion = (suggestion: SettlementSuggestionResponse) => {
    form.setValue("settlement_id", suggestion.settlement_id, {
      shouldDirty: true,
    });
    form.setValue("modern_settlement_name", suggestion.title, {
      shouldDirty: true,
    });
    form.setValue("settlement_category", suggestion.category, {
      shouldDirty: true,
    });
  };

  const clearSuggestion = () => {
    form.setValue("settlement_id", null, { shouldDirty: true });
  };

  return {
    form,
    onSubmit,
    applySuggestion,
    clearSuggestion,
  };
}
