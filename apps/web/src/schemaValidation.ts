/**
 * Client mirror of the backend `validate_schema_definition`
 * (`packages/backend/src/cadmus/lexicography/domain.py`). Error keys match the
 * server's (`fields[0].children[1].role`) so a 422 response maps straight onto
 * the same editor fields.
 */

import {
  MAX_SCHEMA_DEPTH,
  ROLE_LABELS,
  TYPE_LABELS,
  TYPES_WITH_OPTIONS,
} from "./articleSchemaFields";
import { parseSchemaFields, type SchemaNode } from "./schemaDiff";

const ROLE_VALUES = new Set(Object.keys(ROLE_LABELS));
const TYPE_VALUES = new Set(Object.keys(TYPE_LABELS));

/** `[0, 1]` → `"fields[0].children[1]"`. */
export function nodePathKey(indices: number[]): string {
  return indices
    .map((index, position) =>
      position === 0 ? `fields[${index}]` : `children[${index}]`,
    )
    .join(".");
}

export function validateSchemaDefinition(
  definition: unknown,
): Record<string, string> {
  const fields = parseSchemaFields(definition);
  if (fields.length === 0) {
    return { fields: "Додайте щонайменше одне поле." };
  }
  const errors: Record<string, string> = {};

  const walk = (nodes: SchemaNode[], prefix: number[], depth: number) => {
    const seenNames = new Set<string>();
    nodes.forEach((node, index) => {
      const key = nodePathKey([...prefix, index]);
      const name = node.name.trim();
      if (!name) {
        errors[`${key}.name`] = "Вкажіть назву поля.";
      } else if (seenNames.has(name)) {
        errors[`${key}.name`] = `Назва «${name}» повторюється на цьому рівні.`;
      }
      seenNames.add(name);
      if (!ROLE_VALUES.has(node.role)) {
        errors[`${key}.role`] = "Оберіть роль поля.";
      }
      if (!TYPE_VALUES.has(node.type)) {
        errors[`${key}.type`] = "Оберіть тип поля.";
      } else if ((TYPES_WITH_OPTIONS as Set<string>).has(node.type)) {
        const cleaned = node.options.map((item) => item.trim()).filter(Boolean);
        if (cleaned.length === 0) {
          errors[`${key}.options`] = "Додайте щонайменше одне значення переліку.";
        } else if (new Set(cleaned).size !== cleaned.length) {
          errors[`${key}.options`] = "Значення переліку не мають повторюватися.";
        }
      }
      if (node.children.length > 0) {
        if (depth >= MAX_SCHEMA_DEPTH) {
          errors[`${key}.children`] =
            `Схема підтримує щонайбільше ${MAX_SCHEMA_DEPTH} рівні вкладеності.`;
        } else {
          walk(node.children, [...prefix, index], depth + 1);
        }
      }
    });
  };

  walk(fields, [], 1);
  return errors;
}
