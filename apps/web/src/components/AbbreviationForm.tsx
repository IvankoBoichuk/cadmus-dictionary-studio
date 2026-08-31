import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import type { AbbreviationResponse } from "../api";
import { CATEGORY_OPTIONS } from "../abbreviationCategories";
import { useAbbreviationForm } from "../hooks/useAbbreviationForm";
import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useUnsavedChangesWarning } from "../hooks/useUnsavedChangesWarning";
import { LANGUAGE_OPTIONS } from "../languageOptions";

export function AbbreviationForm({
  dictionaryId,
  editing,
  onSaved,
  onCancel,
}: {
  dictionaryId: string;
  editing: AbbreviationResponse | null;
  onSaved: (saved: AbbreviationResponse) => void;
  onCancel?: () => void;
}) {
  const { form, onSubmit, variantFields, addVariant, removeVariant } =
    useAbbreviationForm(dictionaryId, editing, onSaved);
  const formRef = useRef<HTMLFormElement>(null);
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
        aria-labelledby="abbreviation-form-heading"
        className="form-section"
      >
        <h2 id="abbreviation-form-heading">
          {editing ? "Редагувати скорочення" : "Додати скорочення"}
        </h2>

        <FormField
          control={form.control}
          name="abbreviation"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Скорочення</FormLabel>
              <FormControl>
                <Input spellCheck={false} autoComplete="off" {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="category"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Категорія</FormLabel>
              <Select value={field.value} onValueChange={field.onChange}>
                <FormControl>
                  <SelectTrigger>
                    <SelectValue placeholder="Оберіть категорію" />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  {CATEGORY_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="unresolved"
          render={({ field }) => (
            <FormItem>
              <div className="flex items-center gap-2">
                <FormControl>
                  <Checkbox
                    checked={field.value}
                    onCheckedChange={(checked) => field.onChange(checked === true)}
                  />
                </FormControl>
                <FormLabel>
                  Розшифрування поки невідоме (нерозшифрований запис)
                </FormLabel>
              </div>
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="full_form"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Повна форма</FormLabel>
              <FormControl>
                <Input {...field} />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />

        <FormField
          control={form.control}
          name="language_code"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Мова</FormLabel>
              <Select
                value={field.value || "__none__"}
                onValueChange={(value) =>
                  field.onChange(value === "__none__" ? "" : value)
                }
              >
                <FormControl>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                </FormControl>
                <SelectContent>
                  <SelectItem value="__none__">Не вказано</SelectItem>
                  {LANGUAGE_OPTIONS.map((language) => (
                    <SelectItem key={language.code} value={language.code}>
                      {language.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </FormItem>
          )}
        />

        <fieldset className="border-0 p-0">
          <legend className="p-0 font-bold">Варіанти написання</legend>
          <ol className="my-3 grid list-none gap-[0.6rem] p-0">
            {variantFields.map((variantField, index) => (
              <li
                className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-2"
                key={variantField.id}
              >
                <label className="sr-only" htmlFor={`variant-${index}`}>
                  Варіант написання
                </label>
                <input
                  className="min-h-[2.6rem] rounded-[0.5rem] border border-input px-[0.65rem] py-2"
                  id={`variant-${index}`}
                  {...form.register(`variants.${index}.value`)}
                />
                <Button
                  variant="secondary"
                  size="icon"
                  type="button"
                  onClick={() => removeVariant(index)}
                  aria-label={`Видалити варіант «${
                    form.getValues(`variants.${index}.value`) || "без назви"
                  }»`}
                >
                  ✕
                </Button>
              </li>
            ))}
          </ol>
          <Button variant="secondary" type="button" onClick={addVariant}>
            Додати варіант написання
          </Button>
        </fieldset>

        <FormField
          control={form.control}
          name="note"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Примітка</FormLabel>
              <FormControl>
                <Textarea rows={2} {...field} />
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
