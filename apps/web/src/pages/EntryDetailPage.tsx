import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useParams } from "react-router-dom";

import {
  API,
  apiMessageFrom,
  fieldErrorsFrom,
  type ArticleSchemaResponse,
  type EntryFieldResponse,
  type EntryFieldRole,
  type EntryFragmentResponse,
  type EntryStatus,
} from "../api";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { useAuth } from "../authContext";
import { EntryFieldCrop, EntryFragmentCrop } from "../components/EntryFragmentCrop";
import { formatPercent } from "../format";
import { useArticleSchemas } from "../hooks/useArticleSchemas";
import { useEntry } from "../hooks/useEntry";
import { useEntryExtraction } from "../hooks/useEntryExtraction";

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

const STATUS_LABELS: Record<EntryStatus, string> = {
  draft: "Чернетка",
  ready_to_review: "Очікує перевірки",
  complete: "Завершено",
};

const ORIGIN_LABELS: Record<EntryFieldResponse["origin"], string> = {
  model: "AI",
  rule: "правило",
  manual: "вручну",
};

const ROLE_VALUES = new Set<string>(Object.keys(ROLE_LABELS));

function isEntryFieldRole(value: unknown): value is EntryFieldRole {
  return typeof value === "string" && ROLE_VALUES.has(value);
}

type SchemaFieldOption = { name: string; role: EntryFieldRole; depth: number };

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
      options.push({ name: record.name, role: record.role, depth });
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

function AddFieldForm({
  entryId,
  fragments,
  dictionaryId,
  onCreated,
}: {
  entryId: string;
  fragments: EntryFragmentResponse[];
  dictionaryId: string;
  onCreated: (field: EntryFieldResponse) => void;
}) {
  const { state: schemasState } = useArticleSchemas(dictionaryId);
  const schemaOptions =
    schemasState.status === "loaded"
      ? (() => {
          const schema = activeSchema(schemasState.schemas);
          return schema ? flattenSchemaFields(schema.definition) : [];
        })()
      : [];

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

  const matchIndex = fragment ? fragment.recognized_text.indexOf(sourceText) : -1;
  const textFound = sourceText.trim().length > 0 && matchIndex !== -1;

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
    if (!textFound) {
      setError("Текст поля не знайдено у розпізнаному тексті фрагмента.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const created = await API.entries.createField(entryId, {
        fragment_id: fragment.id,
        field_path: fieldPath,
        role,
        source_text: sourceText,
        source_start: matchIndex,
        source_end: matchIndex + sourceText.length,
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
    <form className="dictionary-form" onSubmit={(event) => void submit(event)}>
      {fragments.length > 1 && (
        <>
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
        </>
      )}

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

      {useCustomPath && (
        <>
          <label htmlFor="add-field-manual-path">Назва поля</label>
          <input
            id="add-field-manual-path"
            name="field_path"
            value={manualPath}
            onChange={(event) => setManualPath(event.target.value)}
            placeholder="напр. meaning[0]…"
          />
          <label htmlFor="add-field-manual-role">Роль</label>
          <select
            id="add-field-manual-role"
            value={manualRole}
            onChange={(event) => setManualRole(event.target.value as EntryFieldRole)}
          >
            {Object.entries(ROLE_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </>
      )}

      <label htmlFor="add-field-source-text">
        Текст поля (як він написаний у фрагменті)
      </label>
      <input
        id="add-field-source-text"
        name="source_text"
        value={sourceText}
        onChange={(event) => setSourceText(event.target.value)}
        aria-invalid={sourceText.trim().length > 0 && !textFound}
      />
      {sourceText.trim().length > 0 && !textFound && (
        <p className="field-error" role="alert">
          Такого тексту немає у розпізнаному тексті фрагмента.
        </p>
      )}

      <div className="form-actions">
        <Button type="submit" disabled={saving || !textFound}>
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
  onSaved,
  onDeleted,
}: {
  entryId: string;
  dictionaryId: string;
  pageNumber: number | null;
  field: EntryFieldResponse;
  onSaved: (field: EntryFieldResponse) => void;
  onDeleted: (fieldId: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState(field.normalized_text ?? field.source_text);
  const [draftRole, setDraftRole] = useState<EntryFieldRole>(field.role);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      const updated = await API.entries.updateField(entryId, field.id, {
        normalized_text: draftText.trim() || null,
        role: draftRole,
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
    <li className="grid gap-2">
      {editing ? (
        <>
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
          <label className="sr-only" htmlFor={`field-text-${field.id}`}>
            Текст поля
          </label>
          <input
            id={`field-text-${field.id}`}
            name="normalized_text"
            value={draftText}
            onChange={(event) => setDraftText(event.target.value)}
          />
          <Button
            variant="secondary"
            type="button"
            onClick={() => void save()}
            disabled={saving}
          >
            Зберегти
          </Button>
          <Button
            variant="secondary"
            type="button"
            onClick={() => setEditing(false)}
          >
            Скасувати
          </Button>
        </>
      ) : (
        <>
          <span>{field.normalized_text ?? field.source_text}</span>
          <Badge className="ml-2">{ORIGIN_LABELS[field.origin]}</Badge>
          {field.confidence !== null && (
            <Badge className="ml-2">
              {formatPercent(field.confidence)}
            </Badge>
          )}
          <Button variant="secondary" type="button" onClick={startEditing}>
            Редагувати
          </Button>
          <Button variant="danger" type="button" onClick={() => void remove()}>
            Видалити
          </Button>
          <EntryFieldCrop
            dictionaryId={dictionaryId}
            pageNumber={pageNumber}
            field={field}
          />
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
  const [completeErrors, setCompleteErrors] = useState<Record<string, string> | null>(
    null,
  );
  const [completeMessage, setCompleteMessage] = useState<string | null>(null);
  const [completing, setCompleting] = useState(false);

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

  const { entry } = state;
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

  const handleFieldSaved = (updated: EntryFieldResponse) => {
    setEntry({
      ...entry,
      fields: entry.fields.map((field) => (field.id === updated.id ? updated : field)),
    });
  };

  const handleFieldDeleted = (fieldId: string) => {
    setEntry({
      ...entry,
      fields: entry.fields.filter((field) => field.id !== fieldId),
    });
  };

  const handleComplete = async () => {
    setCompleting(true);
    setCompleteErrors(null);
    setCompleteMessage(null);
    try {
      const completed = await API.entries.complete(entryId);
      setEntry(completed);
      setCompleteMessage("Статтю позначено завершеною.");
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

  return (
    <>
      <div className="form-section">
        <h2>{entry.headword}</h2>
        <p className="lede">
          Статус: <Badge className="ml-2">{STATUS_LABELS[entry.status]}</Badge>
        </p>
        {entry.fragments.map((fragment) => (
          <div key={fragment.id} className="grid gap-2 mb-4">
            <EntryFragmentCrop dictionaryId={entry.dictionary_id} fragment={fragment} />
            <p className="section-hint">{fragment.recognized_text}</p>
          </div>
        ))}
      </div>

      <div className="form-section" aria-labelledby="extract-heading">
        <h2 id="extract-heading">Автоматичний розбір</h2>
        <Button
          variant="secondary"
          type="button"
          onClick={() => void triggerExtraction()}
          disabled={extracting}
        >
          {extracting ? "Розпізнаємо структуру…" : "Розпізнати структуру"}
        </Button>
        {extractionState.status === "succeeded" && (
          <p className="m-0 text-[0.88rem] text-success-foreground" role="status">
            Знайдено полів: {extractionState.createdFields}
          </p>
        )}
        {extractionState.status === "failed" && (
          <p className="form-error" role="alert">
            {extractionState.message}
          </p>
        )}
      </div>

      <div className="form-section" aria-labelledby="add-field-heading">
        <h2 id="add-field-heading">Додати поле вручну</h2>
        <AddFieldForm
          entryId={entry.id}
          fragments={entry.fragments}
          dictionaryId={entry.dictionary_id}
          onCreated={(field) =>
            setEntry({ ...entry, fields: [...entry.fields, field] })
          }
        />
      </div>

      <div className="form-section">
        <h2>Поля статті</h2>
        {entry.fields.length === 0 ? (
          <p className="lede">Полів ще немає — запустіть автоматичний розбір.</p>
        ) : (
          Array.from(fieldsByRole.entries()).map(([role, fields]) => (
            <div key={role}>
              <h3>{ROLE_LABELS[role]}</h3>
              <ul className="grid list-none gap-4 p-0">
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
                    onSaved={handleFieldSaved}
                    onDeleted={handleFieldDeleted}
                  />
                ))}
              </ul>
            </div>
          ))
        )}
      </div>

      <div className="form-section" aria-labelledby="complete-heading">
        <h2 id="complete-heading">Завершення</h2>
        <Button
          type="button"
          disabled={completing || entry.status === "complete"}
          onClick={() => void handleComplete()}
        >
          {completing ? "Перевіряємо…" : "Позначити статтю завершеною"}
        </Button>
        {completeMessage && (
          <p className="m-0 text-[0.88rem] text-success-foreground" role="status">
            {completeMessage}
          </p>
        )}
        {completeErrors && (
          <ul className="field-error" role="alert">
            {Object.entries(completeErrors).map(([field, message]) => (
              <li key={field}>{message}</li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

export function EntryDetailPage() {
  const { session } = useAuth();
  const { entryId } = useParams<{ entryId: string }>();

  if (session.status === "loading") {
    return (
      <main className="page" id="main-content">
        <p role="status">Завантажуємо робочий простір…</p>
      </main>
    );
  }
  if (session.status !== "authenticated") {
    return <Navigate replace to="/login" />;
  }
  if (!entryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return (
    <main className="page" id="main-content">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Стаття</p>
        <h1 id="page-title">Структура словникової статті</h1>
        <p className="lede">
          Перегляньте та відредагуйте автоматично розпізнані поля статті (BH-148).
        </p>
      </section>
      <div className="dictionary-form">
        <EntryWorkspace entryId={entryId} />
      </div>
    </main>
  );
}
