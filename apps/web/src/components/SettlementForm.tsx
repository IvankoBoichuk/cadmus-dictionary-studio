import { useRef } from "react";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

import type { SettlementMappingResponse } from "../api";
import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useSettlementForm } from "../hooks/useSettlementForm";
import { useUnsavedChangesWarning } from "../hooks/useUnsavedChangesWarning";
import { SettlementSearchCombobox } from "./SettlementSearchCombobox";

export function SettlementForm({
  dictionaryId,
  editing,
  onSaved,
  onCancel,
}: {
  dictionaryId: string;
  editing: SettlementMappingResponse | null;
  onSaved: (saved: SettlementMappingResponse) => void;
  onCancel?: () => void;
}) {
  const { form, onSubmit, applySuggestion, clearSuggestion } = useSettlementForm(
    dictionaryId,
    editing,
    onSaved,
  );
  const formRef = useRef<HTMLFormElement>(null);

  const settlementId = form.watch("settlement_id");
  const modernName = form.watch("modern_settlement_name");
  const category = form.watch("settlement_category");
  const submissionError = form.formState.errors.root?.message;

  useFocusFirstError(
    formRef,
    form.formState.submitCount,
    form.formState.isSubmitting,
  );
  useUnsavedChangesWarning(
    form.formState.isDirty && !form.formState.isSubmitting,
  );

  return (
    <Form {...form}>
      <form
        noValidate
        ref={formRef}
        onSubmit={onSubmit}
        aria-labelledby="settlement-form-heading"
        className="form-section"
      >
        <h2 id="settlement-form-heading">
          {editing ? "Редагувати географічну мітку" : "Додати географічну мітку"}
        </h2>

        <FormField
          control={form.control}
          name="source_label"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Позначка з оригіналу</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="source_note"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Примітка з оригіналу</FormLabel>
              <FormControl>
                <Textarea rows={2} {...field} />
              </FormControl>
            </FormItem>
          )}
        />

        <fieldset className="grid gap-[0.45rem]">
          <legend>Сучасна відповідність (AC8)</legend>
          {settlementId ? (
            <p className="lede">
              Зіставлено з: {modernName || "—"} ({category || "—"}).{" "}
              <Button
                variant="secondary"
                size="icon"
                type="button"
                onClick={clearSuggestion}
              >
                Скасувати зіставлення
              </Button>
            </p>
          ) : (
            <SettlementSearchCombobox
              dictionaryId={dictionaryId}
              onSelect={applySuggestion}
            />
          )}
        </fieldset>

        <FormField
          control={form.control}
          name="modern_settlement_name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Сучасна назва (за потреби вручну)</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="settlement_category"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Категорія (за потреби вручну)</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
            </FormItem>
          )}
        />

        {submissionError && (
          <p className="m-0 text-[0.88rem] text-destructive" role="alert">
            {submissionError}
          </p>
        )}

        <div className="form-actions">
          <Button disabled={form.formState.isSubmitting} type="submit">
            {form.formState.isSubmitting
              ? "Зберігаємо…"
              : editing
                ? "Зберегти зміни"
                : "Додати"}
          </Button>
          {editing && onCancel && (
            <Button variant="secondary" type="button" onClick={onCancel}>
              Скасувати
            </Button>
          )}
        </div>
      </form>
    </Form>
  );
}
