import { useCallback, useMemo, useState } from "react";

import {
  API,
  apiMessageFrom,
  fieldErrorsFrom,
  type ArticleSchemaResponse,
} from "../api";
import { parseSchemaFields, type SchemaNode } from "../schemaDiff";
import { validateSchemaDefinition } from "../schemaValidation";

/** Index path into the field tree: `[]` is the root, `[0]` the first field,
 * `[0, 2]` its third child. */
export type NodePath = number[];

function blankNode(): SchemaNode {
  return {
    name: "",
    role: "other",
    type: "string",
    options: [],
    repeatable: false,
    required: false,
    children: [],
  };
}

function updateAt(
  nodes: SchemaNode[],
  path: NodePath,
  updater: (siblings: SchemaNode[], index: number) => SchemaNode[],
): SchemaNode[] {
  const [head, ...rest] = path;
  if (head === undefined) return nodes;
  if (rest.length === 0) return updater(nodes, head);
  return nodes.map((node, index) =>
    index === head
      ? { ...node, children: updateAt(node.children, rest, updater) }
      : node,
  );
}

function toDefinition(fields: SchemaNode[]): { fields: unknown[] } {
  const strip = (node: SchemaNode): Record<string, unknown> => ({
    name: node.name.trim(),
    role: node.role,
    type: node.type,
    options:
      node.type === "enum"
        ? node.options.map((option) => option.trim()).filter(Boolean)
        : [],
    repeatable: node.repeatable,
    required: node.required,
    children: node.children.map(strip),
  });
  return { fields: fields.map(strip) };
}

/**
 * State for the structured article-schema editor. Editing never mutates a
 * version — `submit()` POSTs a brand-new `ready` (inactive) version.
 */
export function useArticleSchemaEditor({
  dictionaryId,
  initial,
  onSaved,
}: {
  dictionaryId: string;
  initial: ArticleSchemaResponse | null;
  onSaved: (saved: ArticleSchemaResponse) => void;
}) {
  const [fields, setFields] = useState<SchemaNode[]>(() =>
    initial ? parseSchemaFields(initial.definition) : [],
  );
  const [sourceDescription, setSourceDescription] = useState(
    initial?.source_description ?? "",
  );
  const [presentationFormula, setPresentationFormula] = useState(
    initial?.presentation_formula ?? "",
  );
  const [submitting, setSubmitting] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [rootError, setRootError] = useState<string | null>(null);

  const clearError = useCallback((key: string) => {
    setErrors((current) => {
      if (!(key in current)) return current;
      const next = { ...current };
      delete next[key];
      return next;
    });
  }, []);

  const updateNode = useCallback(
    (path: NodePath, patch: Partial<SchemaNode>) => {
      setFields((current) =>
        updateAt(current, path, (siblings, index) =>
          siblings.map((node, i) =>
            i === index ? { ...node, ...patch } : node,
          ),
        ),
      );
    },
    [],
  );

  const removeNode = useCallback((path: NodePath) => {
    setFields((current) =>
      updateAt(current, path, (siblings, index) =>
        siblings.filter((_, i) => i !== index),
      ),
    );
  }, []);

  const moveNode = useCallback((path: NodePath, direction: -1 | 1) => {
    setFields((current) =>
      updateAt(current, path, (siblings, index) => {
        const target = index + direction;
        if (target < 0 || target >= siblings.length) return siblings;
        const next = [...siblings];
        const moved = next[index]!;
        next[index] = next[target]!;
        next[target] = moved;
        return next;
      }),
    );
  }, []);

  const appendChild = useCallback((path: NodePath) => {
    setFields((current) =>
      path.length === 0
        ? [...current, blankNode()]
        : updateAt(current, path, (siblings, index) =>
            siblings.map((node, i) =>
              i === index
                ? { ...node, children: [...node.children, blankNode()] }
                : node,
            ),
          ),
    );
  }, []);

  const definition = useMemo(() => toDefinition(fields), [fields]);

  const submit = useCallback(async () => {
    setRootError(null);
    const validation = validateSchemaDefinition(definition);
    if (!presentationFormula.trim()) {
      validation.presentation_formula = "Додайте формулу подання статті.";
    }
    if (Object.keys(validation).length > 0) {
      setErrors(validation);
      setRootError("Виправте позначені поля перед збереженням.");
      return;
    }
    setErrors({});
    setSubmitting(true);
    try {
      const saved = await API.articleSchemas.save(dictionaryId, {
        definition: definition as { [key: string]: unknown },
        source_description: sourceDescription.trim() || null,
        presentation_formula: presentationFormula.trim() || null,
      });
      onSaved(saved);
    } catch (error) {
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors) {
        setErrors(apiErrors);
        setRootError("Сервер відхилив схему. Перевірте позначені поля.");
      } else {
        setRootError(
          apiMessageFrom(error) ??
            "Не вдалося зберегти схему. Спробуйте ще раз.",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }, [
    definition,
    dictionaryId,
    onSaved,
    sourceDescription,
    presentationFormula,
  ]);

  return {
    fields,
    errors,
    rootError,
    submitting,
    sourceDescription,
    setSourceDescription,
    presentationFormula,
    setPresentationFormula,
    appendChild,
    updateNode,
    removeNode,
    moveNode,
    clearError,
    submit,
  };
}
