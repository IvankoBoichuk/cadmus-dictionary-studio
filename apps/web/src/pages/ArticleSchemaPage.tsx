import { useState } from "react";
import { Navigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { API, apiMessageFrom, type ArticleSchemaResponse } from "../api";
import { useArticleSchemaGeneration } from "../hooks/useArticleSchemaGeneration";
import { useArticleSchemas } from "../hooks/useArticleSchemas";

const STATUS_LABELS: Record<ArticleSchemaResponse["status"], string> = {
  pending: "Очікує",
  running: "Генерується",
  ready: "Готова",
  failed: "Помилка",
};

type SchemaFieldNode = {
  name?: unknown;
  role?: unknown;
  type?: unknown;
  repeatable?: unknown;
  required?: unknown;
  children?: unknown;
};

function isFieldNode(value: unknown): value is SchemaFieldNode {
  return typeof value === "object" && value !== null;
}

function SchemaFieldTree({ nodes }: { nodes: unknown }) {
  if (!Array.isArray(nodes) || nodes.length === 0) return null;
  return (
    <ul className="my-2 grid list-disc gap-1 pl-5">
      {nodes.map((node, index) => {
        if (!isFieldNode(node)) return null;
        const name = typeof node.name === "string" ? node.name : "(без назви)";
        const role = typeof node.role === "string" ? node.role : null;
        const type = typeof node.type === "string" ? node.type : null;
        return (
          <li key={index}>
            <span className="font-[650]">{name}</span>
            {role && <Badge className="ml-2"> {role}</Badge>}
            {type && <Badge className="ml-2"> {type}</Badge>}
            {node.repeatable === true && (
              <Badge className="ml-2"> повторюване</Badge>
            )}
            {node.required === true && (
              <Badge className="ml-2"> обов'язкове</Badge>
            )}
            <SchemaFieldTree nodes={node.children} />
          </li>
        );
      })}
    </ul>
  );
}

function ActiveSchema({ schema }: { schema: ArticleSchemaResponse | undefined }) {
  if (!schema) {
    return <p className="lede">Активної схеми ще немає.</p>;
  }
  const fields =
    typeof schema.definition === "object" &&
    schema.definition !== null &&
    "fields" in schema.definition
      ? (schema.definition as { fields: unknown }).fields
      : null;
  return (
    <div className="form-section">
      <h2>Активна схема (версія {schema.version})</h2>
      <SchemaFieldTree nodes={fields} />
    </div>
  );
}

function ArticleSchemaWorkspace({ dictionaryId }: { dictionaryId: string }) {
  const { state, reload } = useArticleSchemas(dictionaryId);
  const { state: generationState, trigger } = useArticleSchemaGeneration(dictionaryId);
  const [activateError, setActivateError] = useState<string | null>(null);

  const generating =
    generationState.status === "starting" ||
    generationState.status === "queued" ||
    generationState.status === "running";

  const schemas = state.status === "loaded" ? state.schemas : [];
  const activeSchema = schemas.find((schema) => schema.activated_at !== null);

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

  return (
    <>
      <div className="form-section" aria-labelledby="generate-heading">
        <h2 id="generate-heading">Генерація схеми</h2>
        <p className="section-hint">
          На основі опису структури статті (у метаданих словника) AI
          запропонує схему полів для автоматичного розбору статей.
        </p>
        <Button
          variant="secondary"
          type="button"
          onClick={() => void trigger()}
          disabled={generating}
        >
          {generating ? "Генеруємо схему…" : "Згенерувати схему"}
        </Button>
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
      </div>

      <ActiveSchema schema={activeSchema} />

      {state.status === "loading" && <p role="status">Завантажуємо версії схеми…</p>}
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
            <ul>
              {schemas.map((schema) => (
                <li key={schema.id}>
                  Версія {schema.version} —{" "}
                  <Badge className="ml-2">
                    {STATUS_LABELS[schema.status]}
                  </Badge>
                  {schema.activated_at && " · активна"}
                  {schema.error_message && (
                    <span className="field-error"> {schema.error_message}</span>
                  )}
                  {schema.status === "ready" && !schema.activated_at && (
                    <Button
                      variant="secondary"
                      type="button"
                      onClick={() => void handleActivate(schema.id)}
                    >
                      Активувати
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
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
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Словник</p>
        <h1 id="page-title">Схема словникової статті</h1>
        <p className="lede">
          Керуйте AI-згенерованою схемою полів статті та її версіями (BH-148).
        </p>
      </section>
      <div className="dictionary-form">
        <ArticleSchemaWorkspace dictionaryId={dictionaryId} />
      </div>
    </>
  );
}
