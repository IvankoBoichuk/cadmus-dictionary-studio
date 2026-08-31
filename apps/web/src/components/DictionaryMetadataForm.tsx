import { FileDown } from "lucide-react";
import { useRef, type ReactNode } from "react";

import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import {
  dictionarySourceDownloadUrl,
  type ContributorRole,
  type DictionaryResponse,
  type LegalStatus,
} from "../api";
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

/** Download icon + tooltip carrying the original file name (BH-27 source panel,
 * condensed into the sticky header). */
function SourceDownload({
  dictionaryId,
  source,
}: {
  dictionaryId: string;
  source: NonNullable<DictionaryResponse["source"]>;
}) {
  const details = [
    formatBytes(source.byte_size),
    source.inspection_status === "verified" && source.page_count !== null
      ? `${source.page_count} стор.`
      : null,
    source.inspection_status === "pending" ? "перевіряємо PDF…" : null,
    source.inspection_status === "failed"
      ? "PDF не пройшов перевірку структури"
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <a
          href={dictionarySourceDownloadUrl(dictionaryId)}
          download
          className={cn(
            buttonVariants({ variant: "secondary", size: "icon" }),
            "size-9",
          )}
        >
          <FileDown aria-hidden="true" />
          <span className="sr-only">
            Завантажити оригінал: {source.original_filename}
            {details ? ` (${details})` : ""}
          </span>
        </a>
      </TooltipTrigger>
      <TooltipContent side="bottom">
        <span className="block font-[650]" translate="no">
          {source.original_filename}
        </span>
        {details && (
          <span className="block text-primary-foreground/80">{details}</span>
        )}
      </TooltipContent>
    </Tooltip>
  );
}

export function DictionaryMetadataForm({
  initialDictionary,
  source,
  onSaved,
  title,
  description,
  statusSlot,
  navSlot,
}: {
  initialDictionary: DictionaryResponse;
  source?: DictionaryResponse["source"];
  onSaved?: (dictionary: DictionaryResponse) => void;
  title?: string;
  description?: string;
  statusSlot?: ReactNode;
  navSlot?: ReactNode;
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

  const hasFeedback =
    missingRequiredFields.length > 0 || Boolean(message) || Boolean(submissionError);

  return (
    <Form {...form}>
      <form
        noValidate
        ref={formRef}
        onSubmit={onSubmit}
        aria-labelledby="page-title"
      >
        <header className="sticky top-0 z-20 -mx-[clamp(1rem,4vw,2.5rem)] -mt-[clamp(2rem,6vw,3.5rem)] mb-6 border-b border-border bg-background/90 px-[clamp(1rem,4vw,2.5rem)] py-3 backdrop-blur-sm">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
            <div className="min-w-0">
              <p className="text-[0.7rem] font-[750] tracking-[0.12em] text-muted-foreground uppercase">
                Словник
              </p>
              <h1 className="mt-0.5 mb-0 max-w-none font-serif text-[1.4rem] leading-tight font-medium">
                {title ?? "Метадані словника"}
              </h1>
              {description && (
                <p className="mt-1 mb-0 hidden truncate text-[0.82rem] text-muted-foreground md:block">
                  {description}
                </p>
              )}
            </div>
            <div className="flex items-center gap-3">
              {source && (
                <SourceDownload
                  dictionaryId={initialDictionary.id}
                  source={source}
                />
              )}
              {statusSlot}
              <Button disabled={form.formState.isSubmitting} type="submit">
                {form.formState.isSubmitting ? "Зберігаємо…" : "Зберегти чернетку"}
              </Button>
            </div>
          </div>
        </header>

        {navSlot}

        {hasFeedback && (
          <div className="mb-6 grid gap-2">
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
              <p
                className="m-0 text-[0.88rem] text-success-foreground"
                role="status"
              >
                {message}
              </p>
            )}
            {submissionError && (
              <p className="m-0 text-[0.88rem] text-destructive" role="alert">
                {submissionError}
              </p>
            )}
          </div>
        )}

        <Card className="grid gap-8 p-[clamp(1.25rem,4vw,2rem)]">
          <section className="grid gap-4" aria-labelledby="bibliographic-heading">
            <h2 id="bibliographic-heading" className="mb-0 text-[1.15rem]">
              Бібліографічні дані
            </h2>

            <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
              <FormField
                control={form.control}
                name="title"
                render={({ field }) => (
                  <FormItem className="sm:col-span-full">
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
                  <FormItem className="sm:col-span-full">
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
                  <FormItem className="sm:col-span-full">
                    <FormLabel>Структура словникової статті</FormLabel>
                    <FormDescription>
                      Опишіть, з яких частин складається словникова стаття
                      (значення, приклади, синоніми тощо) — на основі цього опису
                      система згенерує схему для автоматичного розбору статей.
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
            </div>

            <fieldset className="border-0 p-0">
              <legend className="p-0 font-bold">Автори та укладачі</legend>
              <ol className="my-3 grid max-w-3xl list-none gap-[0.6rem] p-0">
                {contributorFields.map((contributorField, index) => {
                  const name = contributors[index]?.name ?? "";
                  return (
                    <li
                      className="grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-2"
                      key={contributorField.id}
                    >
                      <label
                        className="sr-only"
                        htmlFor={`contributor-name-${index}`}
                      >
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
          </section>

          <div className="h-px bg-border" role="presentation" />

          <div className="grid gap-8 lg:grid-cols-2 lg:items-start">
            <section
              className="grid content-start gap-3"
              aria-labelledby="languages-heading"
            >
              <h2 id="languages-heading" className="mb-0 text-[1.15rem]">
                Мови
              </h2>
              <p className="m-0 text-[0.9rem] text-muted-foreground">
                Оберіть одну чи декілька мов словника.
              </p>
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
            </section>

            <section
              className="grid content-start gap-4"
              aria-labelledby="legal-heading"
            >
              <h2 id="legal-heading" className="mb-0 text-[1.15rem]">
                Правовий статус
              </h2>

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
                        <SelectItem value={LEGAL_STATUS_UNSET}>
                          Не вказано
                        </SelectItem>
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
            </section>
          </div>
        </Card>
      </form>
    </Form>
  );
}
