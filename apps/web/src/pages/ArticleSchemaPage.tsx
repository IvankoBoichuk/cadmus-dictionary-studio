import { useMemo, useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { API, apiMessageFrom, type ArticleSchemaResponse } from "../api";
import { SchemaDiffView } from "../components/SchemaDiffView";
import { SchemaFieldTree } from "../components/SchemaFieldTree";
import { SchemaFieldTreeEditor } from "../components/SchemaFieldTreeEditor";
import { useArticleSchemaEditor } from "../hooks/useArticleSchemaEditor";
import { useArticleSchemaGeneration } from "../hooks/useArticleSchemaGeneration";
import { useArticleSchemas } from "../hooks/useArticleSchemas";

const STATUS_LABELS: Record<ArticleSchemaResponse["status"], string> = {
  pending: "Очікує",
  running: "Генерується",
  ready: "Готова",
  failed: "Помилка",
};

const STATUS_VARIANT: Record<
  ArticleSchemaResponse["status"],
  "secondary" | "info" | "warning" | "danger"
> = {
  pending: "warning",
  running: "info",
  ready: "secondary",
  failed: "danger",
};

function formatDate(iso: string): string {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime())
    ? iso
    : parsed.toLocaleString("uk-UA", { dateStyle: "medium", timeStyle: "short" });
}

function SchemaMeta({ schema }: { schema: ArticleSchemaResponse }) {
  return (
    <dl className="m-0 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[0.85rem]">
      <dt className="text-muted-foreground">Версія</dt>
      <dd className="m-0">{schema.version}</dd>
      <dt className="text-muted-foreground">Статус</dt>
      <dd className="m-0">
        <Badge variant={STATUS_VARIANT[schema.status]}>
          {STATUS_LABELS[schema.status]}
        </Badge>
        {schema.activated_at && (
          <Badge className="ml-2" variant="info">
            активна
          </Badge>
        )}
      </dd>
      <dt className="text-muted-foreground">Створено</dt>
      <dd className="m-0">{formatDate(schema.created_at)}</dd>
      {schema.provider_name && (
        <>
          <dt className="text-muted-foreground">Джерело</dt>
          <dd className="m-0" translate="no">
            {schema.provider_name}
          </dd>
        </>
      )}
      {schema.source_description && (
        <>
          <dt className="text-muted-foreground">Опис структури</dt>
          <dd className="m-0">{schema.source_description}</dd>
        </>
      )}
    </dl>
  );
}

/** Blank editor or one seeded from an existing version. Mounted only while
 * editing, so `useArticleSchemaEditor` runs unconditionally. */
function SchemaEditorPanel({
  dictionaryId,
  initial,
  onSaved,
  onCancel,
}: {
  dictionaryId: string;
  initial: ArticleSchemaResponse | null;
  onSaved: (saved: ArticleSchemaResponse) => void;
  onCancel: () => void;
}) {
  const editor = useArticleSchemaEditor({ dictionaryId, initial, onSaved });

  return (
    <div className="form-section" aria-labelledby="schema-editor-heading">
      <h2 id="schema-editor-heading">
        {initial
          ? `Редагування на основі версії ${initial.version}`
          : "Нова схема вручну"}
      </h2>
      <p className="section-hint">
        Збереження створює нову версію зі статусом «Готова». Вона не стає
        активною, доки ви її не активуєте.
      </p>

      <label className="grid gap-1 text-[0.85rem]">
        Опис структури (необов'язково)
        <input
          className="min-h-[2.6rem] rounded-[0.5rem] border border-input px-[0.65rem] py-2"
          value={editor.sourceDescription}
          onChange={(event) => editor.setSourceDescription(event.target.value)}
        />
      </label>

      <SchemaFieldTreeEditor editor={editor} />

      {editor.rootError && (
        <p className="form-error" role="alert">
          {editor.rootError}
        </p>
      )}

      <div className="form-actions">
        <Button
          type="button"
          disabled={editor.submitting}
          onClick={() => void editor.submit()}
        >
          {editor.submitting ? "Зберігаємо…" : "Зберегти як нову версію"}
        </Button>
        <Button variant="secondary" type="button" onClick={onCancel}>
          Скасувати
        </Button>
      </div>
    </div>
  );
}

function DiffPanel({ schemas }: { schemas: ArticleSchemaResponse[] }) {
  const ordered = useMemo(
    () => [...schemas].sort((a, b) => b.version - a.version),
    [schemas],
  );
  const [baseId, setBaseId] = useState(() => ordered[1]?.id ?? "");
  const [compareId, setCompareId] = useState(() => ordered[0]?.id ?? "");

  const base = ordered.find((schema) => schema.id === baseId);
  const compare = ordered.find((schema) => schema.id === compareId);

  return (
    <div className="form-section" aria-labelledby="schema-diff-heading">
      <h2 id="schema-diff-heading">Порівняння версій</h2>
      <div className="flex flex-wrap gap-3">
        <label className="grid gap-1 text-[0.85rem]">
          Базова версія
          <Select value={baseId} onValueChange={setBaseId}>
            <SelectTrigger className="min-w-[10rem]" aria-label="Базова версія">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ordered.map((schema) => (
                <SelectItem key={schema.id} value={schema.id}>
                  Версія {schema.version}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
        <label className="grid gap-1 text-[0.85rem]">
          Порівняти з
          <Select value={compareId} onValueChange={setCompareId}>
            <SelectTrigger
              className="min-w-[10rem]"
              aria-label="Версія для порівняння"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ordered.map((schema) => (
                <SelectItem key={schema.id} value={schema.id}>
                  Версія {schema.version}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </label>
      </div>

      {base && compare ? (
        <SchemaDiffView
          base={base.definition}
          compare={compare.definition}
          baseLabel={`версія ${base.version}`}
          compareLabel={`версія ${compare.version}`}
        />
      ) : (
        <p className="lede">Оберіть дві версії для порівняння.</p>
      )}
    </div>
  );
}

function ArticleSchemaWorkspace({ dictionaryId }: { dictionaryId: string }) {
  const { state, upsert, reload } = useArticleSchemas(dictionaryId);
  const { state: generationState, trigger } =
    useArticleSchemaGeneration(dictionaryId);
  const [activateError, setActivateError] = useState<string | null>(null);
  const [viewingId, setViewingId] = useState<string | null>(null);
  const [editing, setEditing] = useState<
    { mode: "new" } | { mode: "edit"; schema: ArticleSchemaResponse } | null
  >(null);
  const [savedHint, setSavedHint] = useState<string | null>(null);

  const generating =
    generationState.status === "starting" ||
    generationState.status === "queued" ||
    generationState.status === "running";

  const schemas = state.status === "loaded" ? state.schemas : [];
  const activeSchema = schemas.find((schema) => schema.activated_at !== null);
  const viewing = schemas.find((schema) => schema.id === viewingId);

  const handleActivate = async (schemaId: string) => {
    setActivateError(null);
    try {
      await API.articleSchemas.activate(dictionaryId, schemaId);
      reload();
    } catch (error) {
      setActivateError(
        apiMessageFrom(error) ?? "Не вдалося активувати цю версію схеми.",
      );
    }
  };

  const handleSaved = (saved: ArticleSchemaResponse) => {
    upsert(saved);
    reload();
    setEditing(null);
    setViewingId(saved.id);
    setSavedHint(
      `Версію ${saved.version} збережено. Активуйте її, щоб застосувати.`,
    );
  };

  return (
    <>
      <div className="form-section" aria-labelledby="generate-heading">
        <h2 id="generate-heading">Генерація схеми</h2>
        <p className="section-hint">
          На основі опису структури статті (у метаданих словника) AI
          запропонує схему полів для автоматичного розбору статей.
        </p>
        <div className="form-actions">
          <Button
            variant="secondary"
            type="button"
            onClick={() => void trigger()}
            disabled={generating}
          >
            {generating ? "Генеруємо схему…" : "Згенерувати схему"}
          </Button>
          <Button
            variant="secondary"
            type="button"
            onClick={() => {
              setEditing({ mode: "new" });
              setSavedHint(null);
            }}
          >
            Створити схему вручну
          </Button>
        </div>
        {generationState.status === "succeeded" && (
          <p className="m-0 text-[0.88rem] text-success-foreground" role="status">
            Схему згенеровано. Перегляньте та активуйте потрібну версію нижче.
          </p>
        )}
        {generationState.status === "failed" && (
          <p className="form-error" role="alert">
            {generationState.message}
          </p>
        )}
        {savedHint && (
          <p className="m-0 text-[0.88rem] text-success-foreground" role="status">
            {savedHint}
          </p>
        )}
      </div>

      {editing && (
        <SchemaEditorPanel
          key={editing.mode === "edit" ? editing.schema.id : "new"}
          dictionaryId={dictionaryId}
          initial={editing.mode === "edit" ? editing.schema : null}
          onSaved={handleSaved}
          onCancel={() => setEditing(null)}
        />
      )}

      {activeSchema ? (
        <div className="form-section">
          <h2>Активна схема (версія {activeSchema.version})</h2>
          <SchemaFieldTree definition={activeSchema.definition} />
          <div className="form-actions">
            <Button
              variant="secondary"
              type="button"
              onClick={() => {
                setEditing({ mode: "edit", schema: activeSchema });
                setSavedHint(null);
              }}
            >
              Редагувати цю схему
            </Button>
          </div>
        </div>
      ) : (
        <p className="lede">Активної схеми ще немає.</p>
      )}

      {state.status === "loading" && (
        <p role="status">Завантажуємо версії схеми…</p>
      )}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "loaded" && (
        <div className="form-section">
          <h2>Історія версій</h2>
          {activateError && (
            <p className="form-error" role="alert">
              {activateError}
            </p>
          )}
          {schemas.length === 0 ? (
            <p className="lede">Схему ще не генерували.</p>
          ) : (
            <ul className="m-0 grid list-none gap-2 p-0">
              {[...schemas]
                .sort((a, b) => b.version - a.version)
                .map((schema) => (
                  <li
                    key={schema.id}
                    className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-md border border-border px-3 py-2 text-[0.9rem]"
                  >
                    <span className="font-[650]">Версія {schema.version}</span>
                    <Badge variant={STATUS_VARIANT[schema.status]}>
                      {STATUS_LABELS[schema.status]}
                    </Badge>
                    {schema.activated_at && (
                      <Badge variant="info">активна</Badge>
                    )}
                    {schema.error_message && (
                      <span className="field-error">{schema.error_message}</span>
                    )}
                    <span className="ml-auto flex gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        type="button"
                        onClick={() =>
                          setViewingId((current) =>
                            current === schema.id ? null : schema.id,
                          )
                        }
                      >
                        {viewingId === schema.id ? "Сховати" : "Переглянути"}
                      </Button>
                      <Button
                        variant="secondary"
                        size="sm"
                        type="button"
                        onClick={() => {
                          setEditing({ mode: "edit", schema });
                          setSavedHint(null);
                        }}
                      >
                        Редагувати
                      </Button>
                      {schema.status === "ready" && !schema.activated_at && (
                        <Button
                          variant="secondary"
                          size="sm"
                          type="button"
                          onClick={() => void handleActivate(schema.id)}
                        >
                          Активувати
                        </Button>
                      )}
                    </span>
                  </li>
                ))}
            </ul>
          )}
        </div>
      )}

      {viewing && (
        <div className="form-section" aria-labelledby="schema-viewer-heading">
          <h2 id="schema-viewer-heading">Версія {viewing.version}</h2>
          <SchemaMeta schema={viewing} />
          <SchemaFieldTree definition={viewing.definition} />
        </div>
      )}

      {schemas.length >= 2 && <DiffPanel schemas={schemas} />}
    </>
  );
}

export function ArticleSchemaPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return (
    <>
      <h2 className="mb-2 text-[1.15rem]">Схема словникової статті</h2>
      <p className="max-w-[60ch] text-[0.9rem] text-muted-foreground">
        Керуйте схемою полів статті: генеруйте її AI або редагуйте вручну,
        переглядайте попередні версії та порівнюйте їх між собою (BH-148).
      </p>
      <div className="dictionary-form">
        <ArticleSchemaWorkspace dictionaryId={dictionaryId} />
      </div>
    </>
  );
}
