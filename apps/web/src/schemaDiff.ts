/**
 * Pure helpers for BH-148 article-schema comparison: parse a stored
 * `definition` JSON into a typed node tree, flatten it by dotted name path,
 * and diff two versions field by field.
 */

import type { SchemaFieldType } from "./articleSchemaFields";

export type SchemaNode = {
  name: string;
  role: string;
  type: SchemaFieldType | string;
  options: string[];
  repeatable: boolean;
  required: boolean;
  children: SchemaNode[];
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function parseNode(raw: unknown): SchemaNode | null {
  const record = asRecord(raw);
  if (!record) return null;
  return {
    name: typeof record.name === "string" ? record.name : "",
    role: typeof record.role === "string" ? record.role : "",
    type: typeof record.type === "string" ? record.type : "",
    options: Array.isArray(record.options)
      ? record.options.filter((item): item is string => typeof item === "string")
      : [],
    repeatable: record.repeatable === true,
    required: record.required === true,
    children: Array.isArray(record.children)
      ? record.children
          .map(parseNode)
          .filter((node): node is SchemaNode => node !== null)
      : [],
  };
}

/** Read a stored `definition` (`{ fields: [...] }`) into a typed node list,
 * tolerating partial or malformed data. */
export function parseSchemaFields(definition: unknown): SchemaNode[] {
  const record = asRecord(definition);
  const fields = record?.fields;
  if (!Array.isArray(fields)) return [];
  return fields
    .map(parseNode)
    .filter((node): node is SchemaNode => node !== null);
}

export type FlatNode = { path: string; depth: number; node: SchemaNode };

/** Flatten a node tree into `path -> node`, keyed by the dotted chain of
 * field names (`meaning.example`); unnamed nodes fall back to `[index]`. */
export function flattenSchema(definition: unknown): Map<string, FlatNode> {
  const flat = new Map<string, FlatNode>();
  const walk = (nodes: SchemaNode[], parentPath: string, depth: number) => {
    nodes.forEach((node, index) => {
      const key = node.name.trim() || `[${index}]`;
      const path = parentPath ? `${parentPath}.${key}` : key;
      flat.set(path, { path, depth, node });
      walk(node.children, path, depth + 1);
    });
  };
  walk(parseSchemaFields(definition), "", 0);
  return flat;
}

export type DiffField = "role" | "type" | "options" | "repeatable" | "required";

export type DiffFieldChange = {
  field: DiffField;
  from: string | boolean;
  to: string | boolean;
};

export type DiffKind = "added" | "removed" | "changed" | "unchanged";

export type DiffRow = {
  path: string;
  depth: number;
  kind: DiffKind;
  base?: SchemaNode;
  compare?: SchemaNode;
  changes: DiffFieldChange[];
};

const COMPARED_FIELDS: Exclude<DiffField, "options">[] = [
  "role",
  "type",
  "repeatable",
  "required",
];

function nodeChanges(a: SchemaNode, b: SchemaNode): DiffFieldChange[] {
  const changes: DiffFieldChange[] = [];
  for (const field of COMPARED_FIELDS) {
    if (a[field] !== b[field]) {
      changes.push({ field, from: a[field], to: b[field] });
    }
  }
  const fromOptions = a.options.join(" · ");
  const toOptions = b.options.join(" · ");
  if (fromOptions !== toOptions) {
    changes.push({ field: "options", from: fromOptions, to: toOptions });
  }
  return changes;
}

/**
 * Compare two `definition` JSON values. Rows come in base-traversal order,
 * then any compare-only (added) nodes in their own traversal order.
 */
export function diffSchemas(base: unknown, compare: unknown): DiffRow[] {
  const baseFlat = flattenSchema(base);
  const compareFlat = flattenSchema(compare);
  const rows: DiffRow[] = [];

  for (const [path, { depth, node }] of baseFlat) {
    const other = compareFlat.get(path);
    if (!other) {
      rows.push({ path, depth, kind: "removed", base: node, changes: [] });
      continue;
    }
    const changes = nodeChanges(node, other.node);
    rows.push({
      path,
      depth,
      kind: changes.length > 0 ? "changed" : "unchanged",
      base: node,
      compare: other.node,
      changes,
    });
  }

  for (const [path, { depth, node }] of compareFlat) {
    if (!baseFlat.has(path)) {
      rows.push({ path, depth, kind: "added", compare: node, changes: [] });
    }
  }

  return rows;
}

export type DiffSummary = Record<DiffKind, number>;

export function summarizeDiff(rows: DiffRow[]): DiffSummary {
  const summary: DiffSummary = {
    added: 0,
    removed: 0,
    changed: 0,
    unchanged: 0,
  };
  for (const row of rows) summary[row.kind] += 1;
  return summary;
}
