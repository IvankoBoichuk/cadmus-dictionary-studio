import {
  Check,
  Pencil,
  Plus,
  ScanSearch,
  Sparkles,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Navigate, useParams } from "react-router-dom";

import {
  API,
  apiMessageFrom,
  fieldErrorsFrom,
  type ArticleSchemaResponse,
  type EntryFieldResponse,
  type EntryFieldRole,
  type EntryFragmentResponse,
  type EntryResponse,
  type SettlementMappingResponse,
} from "../api";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { EntryFieldCrop, EntryFragmentCrop } from "../components/EntryFragmentCrop";
import { EntryReferenceLinksSection } from "../components/EntryReferenceLinksSection";
import { EntryRenderPanel } from "../components/EntryRenderPanel";
import { EntryValueCombobox } from "../components/EntryValueCombobox";
import {
  ENTRY_STATUS_LABELS as STATUS_LABELS,
  ENTRY_STATUS_VARIANT as STATUS_VARIANT,
} from "../entryStatusLabels";
import { formatPercent } from "../format";
import { useAbbreviations } from "../hooks/useAbbreviations";
import { useArticleSchemas } from "../hooks/useArticleSchemas";
import { useEntry } from "../hooks/useEntry";
import { useEntryExtraction } from "../hooks/useEntryExtraction";
import { useEntryRender } from "../hooks/useEntryRender";
import { useSettlements } from "../hooks/useSettlements";

const ROLE_LABELS: Record<EntryFieldRole, string> = {
  headword: "Заголовне слово",
  part_of_speech: "Частина мови",
  meaning: "Значення",
  example: "Приклад",
  synonym: "Синонім",
  abbreviation: "Скорочення",
  geographic_label: "Географічна мітка",
  other: "Інше",
};

const ORIGIN_LABELS: Record<EntryFieldResponse["origin"], string> = {
  model: "AI",
  rule: "правило",
  manual: "вручну",
};

const ORIGIN_VARIANT: Record<
  EntryFieldResponse["origin"],
  "info" | "secondary" | "warning"
> = {
  model: "info",
  rule: "secondary",
  manual: "warning",
};

const ROLE_VALUES = new Set<string>(Object.keys(ROLE_LABELS));

function isEntryFieldRole(value: unknown): value is EntryFieldRole {
  return typeof value === "string" && ROLE_VALUES.has(value);
}

type SchemaFieldOption = {
  name: string;
  role: EntryFieldRole;
  depth: number;
  type: string;
  options: string[];
};

/** Leaf segment of an `EntryField.field_path` with any `[index]` suffixes
 * removed (`"senses[0].examples[1]"` → `"examples"`). */
function fieldPathLeaf(fieldPath: string): string {
  const last = fieldPath.split(".").at(-1) ?? "";
  const bracket = last.indexOf("[");
  return bracket === -1 ? last : last.slice(0, bracket);
}

/** Flattens a schema field-tree node list (depth-first) into pickable
 * options. Not a default parameter for `nodes` on purpose: a leaf node's
 * `children` key is often entirely absent (`undefined`) rather than `[]`,
 * and a default parameter resolves `undefined` back to the *top-level*
 * list -- silently restarting the walk from the root on every leaf and
 * recursing forever. */
function flattenSchemaNodes(nodes: unknown, depth: number): SchemaFieldOption[] {
  if (!Array.isArray(nodes)) return [];
  const options: SchemaFieldOption[] = [];
  for (const node of nodes) {
    if (typeof node !== "object" || node === null) continue;
    const record = node as Record<string, unknown>;
    if (typeof record.name === "string" && isEntryFieldRole(record.role)) {
      options.push({
        name: record.name,
        role: record.role,
        depth,
        type: typeof record.type === "string" ? record.type : "string",
        options: Array.isArray(record.options)
          ? record.options.filter(
              (item): item is string => typeof item === "string",
            )
          : [],
      });
    }
    options.push(...flattenSchemaNodes(record.children, depth + 1));
  }
  return options;
}

/** Flattens an activated article schema's field tree, so a manually added
 * field can be tied to the same `field_path`/`role` the schema (and AI
 * extraction) already use. */
function flattenSchemaFields(definition: Record<string, unknown>): SchemaFieldOption[] {
  return flattenSchemaNodes(definition.fields, 0);
}

function activeSchema(schemas: ArticleSchemaResponse[]): ArticleSchemaResponse | null {
  return schemas.find((schema) => schema.activated_at !== null) ?? null;
}

/** A single compact, tooltip-labelled row action (revealed on hover/focus). */
function RowAction({
  label,
  icon: Icon,
  onClick,
  variant = "secondary",
  disabled,
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  variant?: "secondary" | "danger";
  disabled?: boolean;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          size="icon-sm"
          variant={variant}
          type="button"
          onClick={onClick}
          disabled={disabled}
          aria-label={label}
        >
          <Icon aria-hidden="true" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

function StatTile({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="grid min-w-[7rem] gap-0.5 rounded-md border border-border bg-surface px-3 py-2">
      <span className="text-[0.68rem] font-[700] tracking-[0.08em] text-muted-foreground uppercase">
        {label}
      </span>
      <span className="text-[1.05rem] font-[650] tabular-nums">{value}</span>
    </div>
  );
}

/** BH-29 abbreviation / BH-30 settlement lists a reference-typed field is
 * picked from. `null` for every other field type. */
function referenceItems(
  type: string | undefined,
  abbreviationItems: string[],
  settlementItems: string[],
): string[] | null {
  if (type === "abbreviation") return abbreviationItems;
  if (type === "geographic_label") return settlementItems;
  return null;
}

const REFERENCE_LABEL: Record<string, string> = {
  abbreviation: "Скорочення",
  geographic_label: "Географічна мітка",
};

function AddFieldForm({
  entryId,
  fragments,
  schemaOptions,
  abbreviationItems,
  settlementItems,
  onCreated,
}: {
  entryId: string;
  fragments: EntryFragmentResponse[];
  schemaOptions: SchemaFieldOption[];
  abbreviationItems: string[];
  settlementItems: string[];
  onCreated: (field: EntryFieldResponse) => void;
}) {
  const firstFragment = fragments[0] as EntryFragmentResponse | undefined;
  const [fragmentId, setFragmentId] = useState(firstFragment?.id ?? "");
  const [selectedPath, setSelectedPath] = useState(
    schemaOptions.length > 0 ? schemaOptions[0]!.name : "custom",
  );
  const [manualRole, setManualRole] = useState<EntryFieldRole>("other");
  const [manualPath, setManualPath] = useState("");
  const [sourceText, setSourceText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fragment = fragments.find((candidate) => candidate.id === fragmentId);
  const useCustomPath = selectedPath === "custom" || schemaOptions.length === 0;
  const chosenOption = schemaOptions.find((option) => option.name === selectedPath);

  const isEnum =
    !useCustomPath &&
    chosenOption?.type === "enum" &&
    chosenOption.options.length > 0;
  const refItems = useCustomPath
    ? null
    : referenceItems(chosenOption?.type, abbreviationItems, settlementItems);
  const isReference = refItems !== null;

  const matchIndex = fragment ? fragment.recognized_text.indexOf(sourceText) : -1;
  const textFound = sourceText.trim().length > 0 && matchIndex !== -1;
  // Enum and reference values are a controlled vocabulary, not necessarily a
  // substring of the OCR text, so the "text appears in the fragment" gate does
  // not apply. A reference value outside the dictionary's list is still allowed
  // (soft hint only).
  const valueOk = isEnum
    ? (chosenOption?.options ?? []).includes(sourceText.trim())
    : isReference
      ? sourceText.trim().length > 0
      : textFound;
  const refNotInList =
    isReference &&
    sourceText.trim().length > 0 &&
    !(refItems ?? []).includes(sourceText.trim());

  const reset = () => {
    setSourceText("");
    setError(null);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!fragment) return;
    const fieldPath = useCustomPath ? manualPath.trim() : (chosenOption?.name ?? "");
    const role = useCustomPath ? manualRole : (chosenOption?.role ?? "other");
    if (!fieldPath) {
      setError("Вкажіть шлях поля.");
      return;
    }
    if (!valueOk) {
      setError(
        isEnum
          ? "Оберіть значення зі списку."
          : isReference
            ? "Вкажіть значення."
            : "Текст поля не знайдено у розпізнаному тексті фрагмента.",
      );
      return;
    }
    const spanStart = matchIndex >= 0 ? matchIndex : 0;
    const spanEnd = matchIndex >= 0 ? matchIndex + sourceText.length : 0;
    setSaving(true);
    setError(null);
    try {
      const created = await API.entries.createField(entryId, {
        fragment_id: fragment.id,
        field_path: fieldPath,
        role,
        source_text: sourceText,
        source_start: spanStart,
        source_end: spanEnd,
      });
      onCreated(created);
      reset();
    } catch (submitError) {
      const errors = fieldErrorsFrom(submitError);
      setError(
        errors?.source_text ??
          apiMessageFrom(submitError) ??
          "Не вдалося додати поле.",
      );
    } finally {
      setSaving(false);
    }
  };

  if (!fragment) {
    return <p className="lede">Немає фрагмента, до якого можна додати поле.</p>;
  }

  return (
    <form
      className="grid gap-3 text-[0.9rem]"
      onSubmit={(event) => void submit(event)}
    >
      {fragments.length > 1 && (
        <div className="form-field">
          <label htmlFor="add-field-fragment">Фрагмент</label>
          <select
            id="add-field-fragment"
            value={fragmentId}
            onChange={(event) => setFragmentId(event.target.value)}
          >
            {fragments.map((candidate, index) => (
              <option key={candidate.id} value={candidate.id}>
                Фрагмент {index + 1}
                {candidate.page_number ? ` (сторінка ${candidate.page_number})` : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="form-field">
        <label htmlFor="add-field-path">Поле схеми</label>
        <select
          id="add-field-path"
          value={selectedPath}
          onChange={(event) => setSelectedPath(event.target.value)}
        >
          {schemaOptions.map((option) => (
            <option key={option.name} value={option.name}>
              {"— ".repeat(option.depth)}
              {option.name} ({ROLE_LABELS[option.role]})
            </option>
          ))}
          <option value="custom">Інше (вказати вручну)</option>
        </select>
      </div>

      {useCustomPath && (
        <>
          <div className="form-field">
            <label htmlFor="add-field-manual-path">Назва поля</label>
            <input
              id="add-field-manual-path"
              name="field_path"
              value={manualPath}
              onChange={(event) => setManualPath(event.target.value)}
              placeholder="напр. meaning[0]…"
            />
          </div>
          <div className="form-field">
            <label htmlFor="add-field-manual-role">Роль</label>
            <select
              id="add-field-manual-role"
              value={manualRole}
              onChange={(event) =>
                setManualRole(event.target.value as EntryFieldRole)
              }
            >
              {Object.entries(ROLE_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </>
      )}

      <div className="form-field">
        {isReference ? (
          <EntryValueCombobox
            label={`${REFERENCE_LABEL[chosenOption?.type ?? ""] ?? "Значення"} (зі списку словника або власне)`}
            value={sourceText}
            onChange={setSourceText}
            items={refItems ?? []}
            placeholder="Почніть вводити…"
          />
        ) : (
          <>
            <label htmlFor="add-field-source-text">
              {isEnum
                ? "Значення"
                : "Текст поля (як він написаний у фрагменті)"}
            </label>
            {isEnum ? (
              <select
                id="add-field-source-text"
                name="source_text"
                value={sourceText}
                onChange={(event) => setSourceText(event.target.value)}
              >
                <option value="">— оберіть значення —</option>
                {(chosenOption?.options ?? []).map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            ) : (
              <input
                id="add-field-source-text"
                name="source_text"
                value={sourceText}
                onChange={(event) => setSourceText(event.target.value)}
                aria-invalid={sourceText.trim().length > 0 && !textFound}
              />
            )}
          </>
        )}
        {!isEnum && !isReference && sourceText.trim().length > 0 && !textFound && (
          <p className="field-error" role="alert">
            Такого тексту немає у розпізнаному тексті фрагмента.
          </p>
        )}
        {refNotInList && (
          <p className="m-0 text-[0.78rem] text-warning-foreground" role="status">
            Значення відсутнє у довіднику словника — його буде збережено як є.
          </p>
        )}
      </div>

      <div className="form-actions mt-1">
        <Button type="submit" size="sm" disabled={saving || !valueOk}>
          {saving ? "Зберігаємо…" : "Додати поле"}
        </Button>
      </div>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}

function FieldRow({
  entryId,
  dictionaryId,
  pageNumber,
  field,
  schemaOptions,
  abbreviationItems,
  settlementItems,
  settlementMappings,
  linked,
  onHoverChange,
  onSaved,
  onDeleted,
}: {
  entryId: string;
  dictionaryId: string;
  pageNumber: number | null;
  field: EntryFieldResponse;
  schemaOptions: SchemaFieldOption[];
  abbreviationItems: string[];
  settlementItems: string[];
  settlementMappings: SettlementMappingResponse[];
  /** Highlighted because the hovered/focused row is its parent or child. */
  linked: boolean;
  onHoverChange: (fieldId: string | null) => void;
  onSaved: (field: EntryFieldResponse) => void;
  onDeleted: (fieldId: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(field.normalized_text ?? field.source_text);
  const [draftRole, setDraftRole] = useState<EntryFieldRole>(field.role);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const schemaNode = schemaOptions.find(
    (option) => option.name === fieldPathLeaf(field.field_path),
  );
  const enumOptions =
    schemaNode?.type === "enum" ? schemaNode.options : [];
  const refItems = referenceItems(
    schemaNode?.type,
    abbreviationItems,
    settlementItems,
  );
  const isReference = refItems !== null;
  const refNotInList =
    isReference &&
    draftText.trim().length > 0 &&
    !(refItems ?? []).includes(draftText.trim());

  const isGeoLabel = field.role === "geographic_label";
  const linkedMapping = isGeoLabel
    ? settlementMappings.find((m) => m.id === field.settlement_mapping_id)
    : undefined;

  const hasCrop =
    pageNumber != null &&
    field.x != null &&
    field.y != null &&
    field.width != null &&
    field.height != null;

  const startEditing = () => {
    setDraftText(field.normalized_text ?? field.source_text);
    setDraftRole(field.role);
    setEditing(true);
    setError(null);
  };

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      const geoNow = draftRole === "geographic_label";
      const mappingId = geoNow
        ? (settlementMappings.find(
            (m) => m.source_label === draftText.trim(),
          )?.id ?? null)
        : undefined;
      const updated = await API.entries.updateField(entryId, field.id, {
        normalized_text: draftText.trim() || null,
        role: draftRole,
        ...(geoNow ? { settlement_mapping_id: mappingId } : {}),
      });
      onSaved(updated);
      setEditing(false);
    } catch (submitError) {
      setError(apiMessageFrom(submitError) ?? "Не вдалося зберегти поле.");
    } finally {
      setSaving(false);
    }
  };

  const remove = async () => {
    if (!window.confirm("Видалити це поле?")) return;
    try {
      await API.entries.deleteField(entryId, field.id);
      onDeleted(field.id);
    } catch (deleteError) {
      setError(apiMessageFrom(deleteError) ?? "Не вдалося видалити поле.");
    }
  };

  return (
    <li
      data-linked={linked || undefined}
      className={cn(
        "group grid gap-1.5 rounded-md border bg-surface p-2 transition-colors",
        linked
          ? "border-lexeme bg-lexeme/5 ring-1 ring-lexeme/40"
          : "border-border",
      )}
      onMouseEnter={() => onHoverChange(field.id)}
      onMouseLeave={() => onHoverChange(null)}
      onFocus={() => onHoverChange(field.id)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
          onHoverChange(null);
        }
      }}
    >
      {editing ? (
        <div className="form-field text-[0.9rem]">
          <label className="sr-only" htmlFor={`field-role-${field.id}`}>
            Роль
          </label>
          <select
            id={`field-role-${field.id}`}
            value={draftRole}
            onChange={(event) => setDraftRole(event.target.value as EntryFieldRole)}
          >
            {Object.entries(ROLE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          {isReference ? (
            <EntryValueCombobox
              label={REFERENCE_LABEL[schemaNode?.type ?? ""] ?? "Значення"}
              value={draftText}
              onChange={setDraftText}
              items={refItems ?? []}
              placeholder="Почніть вводити…"
            />
          ) : (
            <>
              <label className="sr-only" htmlFor={`field-text-${field.id}`}>
                {enumOptions.length > 0 ? "Значення" : "Текст поля"}
              </label>
              {enumOptions.length > 0 ? (
                <select
                  id={`field-text-${field.id}`}
                  name="normalized_text"
                  value={draftText}
                  onChange={(event) => setDraftText(event.target.value)}
                >
                  <option value="">— оберіть значення —</option>
                  {enumOptions.map((option) => (
                    <option key={option} value={option}>
                      {option}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  id={`field-text-${field.id}`}
                  name="normalized_text"
                  value={draftText}
                  onChange={(event) => setDraftText(event.target.value)}
                />
              )}
            </>
          )}
          {refNotInList && (
            <p
              className="m-0 text-[0.78rem] text-warning-foreground"
              role="status"
            >
              Значення відсутнє у довіднику словника — його буде збережено як є.
            </p>
          )}
          <div className="mt-1 flex gap-1">
            <RowAction
              label="Зберегти"
              icon={Check}
              onClick={() => void save()}
              disabled={saving}
            />
            <RowAction
              label="Скасувати"
              icon={X}
              onClick={() => setEditing(false)}
            />
          </div>
        </div>
      ) : (
        <>
          <div className="flex items-start justify-between gap-2">
            <span className="font-[650] [overflow-wrap:anywhere]">
              {field.normalized_text ?? field.source_text}
            </span>
            <div
              className={cn(
                "flex shrink-0 gap-1 transition-opacity",
                "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100",
                "[@media(hover:none)]:opacity-100",
              )}
            >
              <RowAction
                label="Редагувати"
                icon={Pencil}
                onClick={startEditing}
              />
              {hasCrop && (
                <Popover>
                  <PopoverTrigger asChild>
                    <Button
                      size="icon-sm"
                      variant="secondary"
                      type="button"
                      aria-label="Показати на сторінці"
                    >
                      <ScanSearch aria-hidden="true" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent className="w-auto">
                    <EntryFieldCrop
                      dictionaryId={dictionaryId}
                      pageNumber={pageNumber}
                      field={field}
                    />
                  </PopoverContent>
                </Popover>
              )}
              <RowAction
                label="Видалити"
                icon={Trash2}
                variant="danger"
                onClick={() => void remove()}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant={ORIGIN_VARIANT[field.origin]}>
              {ORIGIN_LABELS[field.origin]}
            </Badge>
            {field.confidence !== null && (
              <Badge variant={field.confidence >= 0.8 ? "secondary" : "warning"}>
                {formatPercent(field.confidence)}
              </Badge>
            )}
            <span className="text-[0.72rem] text-muted-foreground tabular-nums [overflow-wrap:anywhere]">
              {field.field_path}
            </span>
          </div>
          {isGeoLabel &&
            (linkedMapping ? (
              <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-2 gap-y-0.5 rounded-md border border-border bg-muted/30 px-2 py-1 text-[0.75rem]">
                <dt className="text-muted-foreground">Населений пункт</dt>
                <dd className="m-0">
                  {linkedMapping.modern_settlement_name ??
                    linkedMapping.source_label}
                </dd>
                <dt className="text-muted-foreground">Район</dt>
                <dd className="m-0">{linkedMapping.district ?? "—"}</dd>
                <dt className="text-muted-foreground">Громада</dt>
                <dd className="m-0">{linkedMapping.community_name ?? "—"}</dd>
                <dt className="text-muted-foreground">Статус</dt>
                <dd className="m-0">
                  <Badge
                    variant={
                      linkedMapping.status === "confirmed"
                        ? "secondary"
                        : linkedMapping.status === "suggested"
                          ? "info"
                          : "warning"
                    }
                  >
                    {linkedMapping.status === "confirmed"
                      ? "підтверджено"
                      : linkedMapping.status === "suggested"
                        ? "запропоновано"
                        : "не зіставлено"}
                  </Badge>
                </dd>
              </dl>
            ) : (
              <p className="m-0 text-[0.75rem] text-muted-foreground">
                Не прив'язано до довідника географічних міток.
              </p>
            ))}
        </>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </li>
  );
}

function EntryWorkspace({ entryId }: { entryId: string }) {
  const { state, setEntry, reload } = useEntry(entryId);
  const { state: extractionState, trigger: triggerExtraction } =
    useEntryExtraction(entryId);

  useEffect(() => {
    if (extractionState.status === "succeeded") reload();
  }, [extractionState.status, reload]);

  if (state.status === "loading") {
    return <p role="status">Завантажуємо статтю…</p>;
  }
  if (state.status === "error") {
    return (
      <p className="form-error" role="alert">
        {state.message}
      </p>
    );
  }

  return (
    <EntryBody
      entry={state.entry}
      setEntry={setEntry}
      extractionState={extractionState}
      triggerExtraction={triggerExtraction}
    />
  );
}

function EntryBody({
  entry,
  setEntry,
  extractionState,
  triggerExtraction,
}: {
  entry: EntryResponse;
  setEntry: (entry: EntryResponse) => void;
  extractionState: ReturnType<typeof useEntryExtraction>["state"];
  triggerExtraction: ReturnType<typeof useEntryExtraction>["trigger"];
}) {
  const { state: schemasState } = useArticleSchemas(entry.dictionary_id);
  const { state: abbreviationsState } = useAbbreviations(entry.dictionary_id);
  const { state: settlementsState } = useSettlements(entry.dictionary_id);
  const { state: renderState, reload: reloadRender } = useEntryRender(entry.id);
  const [completeErrors, setCompleteErrors] = useState<Record<string, string> | null>(
    null,
  );
  const [completeMessage, setCompleteMessage] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [hoveredFieldId, setHoveredFieldId] = useState<string | null>(null);

  /** Ids of the fields directly linked to the hovered one: its parent field
   * plus every field extracted from it (e.g. the geographic labels / abbrevi-
   * ations a rule pass tagged inside an example). Empty when the hovered field
   * has no such relations, so unrelated rows never light up. */
  const linkedFieldIds = useMemo(() => {
    const linked = new Set<string>();
    if (!hoveredFieldId) return linked;
    const hovered = entry.fields.find((field) => field.id === hoveredFieldId);
    if (hovered?.parent_field_id) linked.add(hovered.parent_field_id);
    for (const field of entry.fields) {
      if (field.parent_field_id === hoveredFieldId) linked.add(field.id);
    }
    if (linked.size > 0) linked.add(hoveredFieldId);
    return linked;
  }, [hoveredFieldId, entry.fields]);

  const schemaOptions = useMemo(() => {
    if (schemasState.status !== "loaded") return [];
    const schema = activeSchema(schemasState.schemas);
    return schema ? flattenSchemaFields(schema.definition) : [];
  }, [schemasState]);

  const abbreviationItems = useMemo(
    () =>
      abbreviationsState.status === "loaded" &&
      Array.isArray(abbreviationsState.abbreviations)
        ? abbreviationsState.abbreviations
            .map((item) => item.abbreviation)
            .filter(Boolean)
        : [],
    [abbreviationsState],
  );
  const settlementMappings = useMemo(
    () =>
      settlementsState.status === "loaded" &&
      Array.isArray(settlementsState.mappings)
        ? settlementsState.mappings
        : [],
    [settlementsState],
  );
  const settlementItems = useMemo(
    () => settlementMappings.map((item) => item.source_label).filter(Boolean),
    [settlementMappings],
  );

  const entryId = entry.id;
  const extracting =
    extractionState.status === "starting" ||
    extractionState.status === "queued" ||
    extractionState.status === "running";

  const fieldsByRole = new Map<EntryFieldRole, EntryFieldResponse[]>();
  for (const field of entry.fields) {
    const list = fieldsByRole.get(field.role) ?? [];
    list.push(field);
    fieldsByRole.set(field.role, list);
  }

  const confidences = entry.fields
    .map((field) => field.confidence)
    .filter((value): value is number => value !== null);
  const averageConfidence =
    confidences.length > 0
      ? confidences.reduce((sum, value) => sum + value, 0) / confidences.length
      : null;

  const handleFieldSaved = (updated: EntryFieldResponse) => {
    setEntry({
      ...entry,
      fields: entry.fields.map((field) => (field.id === updated.id ? updated : field)),
    });
    reloadRender();
  };

  const handleFieldDeleted = (fieldId: string) => {
    setEntry({
      ...entry,
      fields: entry.fields.filter((field) => field.id !== fieldId),
    });
    reloadRender();
  };

  const handleComplete = async () => {
    setCompleting(true);
    setCompleteErrors(null);
    setCompleteMessage(null);
    try {
      const completed = await API.entries.complete(entryId);
      setEntry(completed);
      setCompleteMessage("Статтю позначено завершеною.");
      reloadRender();
    } catch (error) {
      const errors = fieldErrorsFrom(error);
      if (errors) {
        setCompleteErrors(errors);
      } else {
        setCompleteErrors({
          _: apiMessageFrom(error) ?? "Не вдалося завершити статтю.",
        });
      }
    } finally {
      setCompleting(false);
    }
  };

  const handleSubmitReview = async () => {
    setCompleting(true);
    setCompleteErrors(null);
    setCompleteMessage(null);
    try {
      const submitted = await API.entries.submitReview(entryId);
      setEntry(submitted);
      setCompleteMessage("Статтю подано на перевірку.");
    } catch (error) {
      const errors = fieldErrorsFrom(error);
      if (errors) {
        setCompleteErrors(errors);
      } else {
        setCompleteErrors({
          _: apiMessageFrom(error) ?? "Не вдалося подати статтю на перевірку.",
        });
      }
    } finally {
      setCompleting(false);
    }
  };

  return (
    <>
      <header className="sticky top-0 z-20 -mx-[clamp(1rem,4vw,2.5rem)] -mt-[clamp(2rem,6vw,3.5rem)] mb-6 border-b border-border bg-background/90 px-[clamp(1rem,4vw,2.5rem)] py-3 backdrop-blur-sm">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <div className="min-w-0">
            <p className="text-[0.7rem] font-[750] tracking-[0.12em] text-muted-foreground uppercase">
              Словникова стаття
            </p>
            <h1 className="mt-0.5 mb-0 max-w-none truncate font-serif text-[1.4rem] leading-tight font-medium">
              {entry.headword}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Badge size="lg" variant={STATUS_VARIANT[entry.status]}>
              {STATUS_LABELS[entry.status]}
            </Badge>
            <Button
              variant="secondary"
              type="button"
              onClick={() => void triggerExtraction()}
              disabled={extracting}
            >
              <Sparkles aria-hidden="true" />
              {extracting ? "Розпізнаємо структуру…" : "Розпізнати структуру"}
            </Button>
            {entry.status === "draft" && (
              <Button
                variant="secondary"
                type="button"
                disabled={completing}
                onClick={() => void handleSubmitReview()}
              >
                {completing ? "Перевіряємо…" : "Подати на перевірку"}
              </Button>
            )}
            <Button
              type="button"
              disabled={completing || entry.status === "complete"}
              onClick={() => void handleComplete()}
            >
              {completing ? "Перевіряємо…" : "Позначити завершеною"}
            </Button>
          </div>
        </div>
        {(extractionState.status === "succeeded" ||
          extractionState.status === "failed" ||
          completeMessage ||
          completeErrors) && (
          <div className="mt-3 grid gap-1.5">
            {extractionState.status === "succeeded" && (
              <p
                className="m-0 text-[0.88rem] text-success-foreground"
                role="status"
              >
                Знайдено полів: {extractionState.createdFields}
              </p>
            )}
            {extractionState.status === "failed" && (
              <p className="form-error" role="alert">
                {extractionState.message}
              </p>
            )}
            {completeMessage && (
              <p
                className="m-0 text-[0.88rem] text-success-foreground"
                role="status"
              >
                {completeMessage}
              </p>
            )}
            {completeErrors && (
              <div
                className="rounded-md bg-warning px-3 py-2 text-[0.88rem] text-warning-foreground"
                role="alert"
              >
                <p className="m-0 font-[650]">
                  Статтю ще не можна завершити:
                </p>
                <ul className="m-0 mt-1 list-disc pl-5">
                  {Object.entries(completeErrors).map(([field, message]) => (
                    <li key={field}>{message}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,34rem)_minmax(0,1fr)] lg:items-start">
        <aside className="min-w-0 lg:sticky lg:top-24 lg:self-start lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto lg:overscroll-contain">
          <div className="form-section">
            <h2>Джерело</h2>
            <p className="section-hint">
              Скан і розпізнаний текст фрагментів, з яких зібрано статтю.
            </p>
            {entry.fragments.map((fragment, index) => (
              <div key={fragment.id} className="grid gap-2">
                {entry.fragments.length > 1 && (
                  <p className="m-0 text-[0.75rem] font-[700] tracking-[0.08em] text-muted-foreground uppercase">
                    Фрагмент {index + 1}
                    {fragment.page_number
                      ? ` · сторінка ${fragment.page_number}`
                      : ""}
                  </p>
                )}
                <EntryFragmentCrop
                  dictionaryId={entry.dictionary_id}
                  fragment={fragment}
                />
                <p className="m-0 rounded-md bg-accent/40 p-2 text-[0.85rem] leading-relaxed [overflow-wrap:anywhere]">
                  {fragment.recognized_text}
                </p>
              </div>
            ))}
          </div>
        </aside>

        <div className="grid min-w-0 gap-6">
          <div className="flex flex-wrap gap-2">
            <StatTile label="Полів" value={entry.fields.length} />
            <StatTile label="Ролей" value={fieldsByRole.size} />
            {averageConfidence !== null && (
              <StatTile
                label="Сер. впевненість"
                value={formatPercent(averageConfidence)}
              />
            )}
          </div>

          <div className="form-section">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="!mb-0">Поля статті</h2>
              <Popover open={addOpen} onOpenChange={setAddOpen}>
                <PopoverTrigger asChild>
                  <Button variant="secondary" size="sm" type="button">
                    <Plus aria-hidden="true" />
                    Додати поле вручну
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="max-h-[70vh] w-[min(92vw,30rem)] overflow-y-auto">
                  <p className="m-0 mb-2 text-[0.8rem] font-[650] text-muted-foreground">
                    Нове поле статті
                  </p>
                  <AddFieldForm
                    entryId={entry.id}
                    fragments={entry.fragments}
                    schemaOptions={schemaOptions}
                    abbreviationItems={abbreviationItems}
                    settlementItems={settlementItems}
                    onCreated={(field) => {
                      setEntry({ ...entry, fields: [...entry.fields, field] });
                      setAddOpen(false);
                      reloadRender();
                    }}
                  />
                </PopoverContent>
              </Popover>
            </div>

            {entry.fields.length === 0 ? (
              <p className="lede">
                Полів ще немає — запустіть автоматичний розбір.
              </p>
            ) : (
              <div className="grid gap-4">
                {Array.from(fieldsByRole.entries()).map(([role, fields]) => (
                  <section key={role} className="grid gap-2">
                    <div className="flex items-center gap-2">
                      <h3 className="m-0 text-[0.95rem]">{ROLE_LABELS[role]}</h3>
                      <Badge variant="secondary">{fields.length}</Badge>
                    </div>
                    <ul className="grid list-none gap-2 p-0 sm:grid-cols-2">
                      {fields.map((field) => (
                        <FieldRow
                          key={field.id}
                          entryId={entry.id}
                          dictionaryId={entry.dictionary_id}
                          pageNumber={
                            entry.fragments.find(
                              (fragment) => fragment.id === field.fragment_id,
                            )?.page_number ?? null
                          }
                          field={field}
                          schemaOptions={schemaOptions}
                          abbreviationItems={abbreviationItems}
                          settlementItems={settlementItems}
                          settlementMappings={settlementMappings}
                          linked={linkedFieldIds.has(field.id)}
                          onHoverChange={setHoveredFieldId}
                          onSaved={handleFieldSaved}
                          onDeleted={handleFieldDeleted}
                        />
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            )}
          </div>

          <EntryRenderPanel state={renderState} />

          <EntryReferenceLinksSection entryId={entryId} />
        </div>
      </div>
    </>
  );
}

export function EntryDetailPage() {
  const { entryId } = useParams<{ entryId: string }>();

  if (!entryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return <EntryWorkspace entryId={entryId} />;
}
