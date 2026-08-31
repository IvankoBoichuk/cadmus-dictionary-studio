import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import type { ContributorRole, DictionaryResponse, LegalStatus } from "../api";
import { formatBytes } from "../hooks/useDictionaryUpload";
import { useDictionaryMetadataForm } from "../hooks/useDictionaryMetadataForm";
import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useUnsavedChangesWarning } from "../hooks/useUnsavedChangesWarning";
import { LANGUAGE_OPTIONS } from "../languageOptions";

const MISSING_FIELD_LABELS: Record<string, string> = {
  title: "Назва",
  languages: "Мови",
  legal_status: "Правовий статус",
};

const LEGAL_STATUS_UNSET = "__unset__";

const LEGAL_STATUS_OPTIONS: { value: LegalStatus; label: string }[] = [
  { value: "public_domain", label: "Суспільне надбання" },
  { value: "licensed", label: "За ліцензією" },
  { value: "permission_granted", label: "Дозвіл отримано" },
  { value: "restricted", label: "Обмежений доступ" },
  { value: "unknown", label: "Невідомо" },
];

const CONTRIBUTOR_ROLE_OPTIONS: { value: ContributorRole; label: string }[] = [
  { value: "compiler", label: "Укладач(ка)" },
  { value: "author", label: "Автор(ка)" },
];

export function DictionaryMetadataForm({
  initialDictionary,
  source,
  onSaved,
}: {
  initialDictionary: DictionaryResponse;
  source?: DictionaryResponse["source"];
  onSaved?: (dictionary: DictionaryResponse) => void;
}) {
  const {
    form,
    onSubmit,
    message,
    submissionError,
    missingRequiredFields,
    contributorFields,
    addContributor,
    removeContributor,
    moveContributor,
    toggleLanguage,
  } = useDictionaryMetadataForm(initialDictionary, onSaved);
  const formRef = useRef<HTMLFormElement>(null);

  useFocusFirstError(
    formRef,
    form.formState.submitCount,
    form.formState.isSubmitting,
  );
  useUnsavedChangesWarning(
    form.formState.isDirty && !form.formState.isSubmitting,
  );

  const contributors = form.watch("contributors");
  const languageCodes = form.watch("language_codes");
  const legalStatus = form.watch("legal_status");

  return (
    <Form {...form}>
      <form
        noValidate
        ref={formRef}
        onSubmit={onSubmit}
        aria-labelledby="metadata-heading"
      >
        {source && (
          <div className="form-section">
            <h2 id="metadata-heading">Джерело</h2>
            <p className="m-0 font-[650] text-primary-strong">
              <span translate="no">{source.original_filename}</span> ·{" "}
              {formatBytes(source.byte_size)}
              {source.inspection_status === "pending" && " · перевіряємо PDF…"}
              {source.inspection_status === "verified" &&
                source.page_count !== null &&
                ` · ${source.page_count} стор.`}
              {source.inspection_status === "failed" &&
                " · PDF не пройшов перевірку структури."}
            </p>
          </div>
        )}

        <div className="form-section" aria-labelledby="bibliographic-heading">
          <h2 id="bibliographic-heading">2. Бібліографічні дані</h2>

          <FormField
            control={form.control}
            name="title"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Назва</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="description"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Опис</FormLabel>
                <FormControl>
                  <Textarea rows={3} {...field} />
                </FormControl>
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="article_description"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Структура словникової статті</FormLabel>
                <FormDescription>
                  Опишіть, з яких частин складається словникова стаття (значення,
                  приклади, синоніми тощо) — на основі цього опису система
                  згенерує схему для автоматичного розбору статей.
                </FormDescription>
                <FormControl>
                  <Textarea rows={6} {...field} />
                </FormControl>
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="dictionary_type"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Тип словника</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="publisher"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Видавництво</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="publication_year"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Рік видання</FormLabel>
                <FormControl>
                  <Input inputMode="numeric" spellCheck={false} {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="edition"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Видання (номер / назва)</FormLabel>
                <FormControl>
                  <Input {...field} />
                </FormControl>
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="isbn"
            render={({ field }) => (
              <FormItem>
                <FormLabel>ISBN</FormLabel>
                <FormControl>
                  <Input spellCheck={false} autoComplete="off" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="digital_source"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Джерело цифрової копії</FormLabel>
                <FormControl>
                  <Input autoComplete="off" {...field} />
                </FormControl>
              </FormItem>
            )}
          />

          <fieldset className="border-0 p-0">
            <legend className="p-0 font-bold">Автори та укладачі</legend>
            <ol className="my-3 grid list-none gap-[0.6rem] p-0">
              {contributorFields.map((contributorField, index) => {
                const name = contributors[index]?.name ?? "";
                return (
                  <li
                    className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-2"
                    key={contributorField.id}
                  >
                    <label className="sr-only" htmlFor={`contributor-name-${index}`}>
                      Ім'я
                    </label>
                    <input
                      className="min-h-[2.6rem] rounded-[0.5rem] border border-input px-[0.65rem] py-2"
                      id={`contributor-name-${index}`}
                      {...form.register(`contributors.${index}.name`)}
                    />
                    <label
                      className="sr-only"
                      htmlFor={`contributor-role-${index}`}
                    >
                      Роль
                    </label>
                    <select
                      className="min-h-[2.6rem] rounded-[0.5rem] border border-input px-[0.65rem] py-2"
                      id={`contributor-role-${index}`}
                      {...form.register(`contributors.${index}.role`)}
                    >
                      {CONTRIBUTOR_ROLE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <Button
                      variant="secondary"
                      size="icon"
                      type="button"
                      onClick={() => moveContributor(index, -1)}
                      disabled={index === 0}
                      aria-label={`Перемістити ${name || "запис"} вище`}
                    >
                      ↑
                    </Button>
                    <Button
                      variant="secondary"
                      size="icon"
                      type="button"
                      onClick={() => moveContributor(index, 1)}
                      disabled={index === contributorFields.length - 1}
                      aria-label={`Перемістити ${name || "запис"} нижче`}
                    >
                      ↓
                    </Button>
                    <Button
                      variant="secondary"
                      size="icon"
                      type="button"
                      onClick={() => removeContributor(index)}
                      aria-label={`Видалити ${name || "запис"}`}
                    >
                      ✕
                    </Button>
                  </li>
                );
              })}
            </ol>
            <Button
              variant="secondary"
              type="button"
              onClick={() => addContributor({ name: "", role: "compiler" })}
            >
              Додати автора чи укладача
            </Button>
          </fieldset>
        </div>

        <div className="form-section" aria-labelledby="languages-heading">
          <h2 id="languages-heading">3. Мови</h2>
          <p className="section-hint">Оберіть одну чи декілька мов словника.</p>
          <div
            className="grid grid-cols-[repeat(auto-fill,minmax(9rem,1fr))] gap-[0.6rem]"
            role="group"
            aria-labelledby="languages-heading"
          >
            {LANGUAGE_OPTIONS.map((language) => (
              <div className="flex items-center gap-2" key={language.code}>
                <Checkbox
                  id={`language-${language.code}`}
                  checked={languageCodes.includes(language.code)}
                  onCheckedChange={() => toggleLanguage(language.code)}
                />
                <Label
                  htmlFor={`language-${language.code}`}
                  className="font-semibold"
                >
                  {language.name}
                </Label>
              </div>
            ))}
          </div>
          {form.formState.errors.language_codes && (
            <p className="m-0 text-[0.88rem] text-destructive" role="alert">
              {form.formState.errors.language_codes.message}
            </p>
          )}
        </div>

        <div className="form-section" aria-labelledby="legal-heading">
          <h2 id="legal-heading">4. Правовий статус</h2>

          <FormField
            control={form.control}
            name="legal_status"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Правовий статус</FormLabel>
                <Select
                  value={field.value || LEGAL_STATUS_UNSET}
                  onValueChange={(value) =>
                    field.onChange(value === LEGAL_STATUS_UNSET ? "" : value)
                  }
                >
                  <FormControl>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                  </FormControl>
                  <SelectContent>
                    <SelectItem value={LEGAL_STATUS_UNSET}>Не вказано</SelectItem>
                    {LEGAL_STATUS_OPTIONS.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {option.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </FormItem>
            )}
          />

          {legalStatus === "licensed" && (
            <FormField
              control={form.control}
              name="license_type"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Тип ліцензії</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}

          {legalStatus === "permission_granted" && (
            <FormField
              control={form.control}
              name="permission_reference"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Ідентифікатор чи опис дозволу</FormLabel>
                  <FormControl>
                    <Input {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          )}

          <FormField
            control={form.control}
            name="rights_note"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Примітка щодо прав</FormLabel>
                <FormControl>
                  <Textarea rows={2} {...field} />
                </FormControl>
              </FormItem>
            )}
          />
        </div>

        <div className="form-section" aria-labelledby="save-heading">
          <h2 id="save-heading">5. Збереження чернетки</h2>
          {missingRequiredFields.length > 0 && (
            <p
              className="rounded-[0.6rem] bg-warning px-4 py-3 text-[0.92rem] text-warning-foreground"
              role="status"
            >
              {"Ще не заповнено: " +
                missingRequiredFields
                  .map((field) => MISSING_FIELD_LABELS[field] ?? field)
                  .join(", ") +
                ". Чернетку можна зберегти й заповнити пізніше."}
            </p>
          )}
          {message && (
            <p className="m-0 text-[0.88rem] text-success-foreground" role="status">
              {message}
            </p>
          )}
          {submissionError && (
            <p className="m-0 text-[0.88rem] text-destructive" role="alert">
              {submissionError}
            </p>
          )}
          <Button disabled={form.formState.isSubmitting} type="submit">
            {form.formState.isSubmitting ? "Зберігаємо…" : "Зберегти чернетку"}
          </Button>
        </div>
      </form>
    </Form>
  );
}
