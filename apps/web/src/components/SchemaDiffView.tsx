import { useState } from "react";

import { Badge } from "@/components/ui/badge";

import { ROLE_LABELS, TYPE_LABELS } from "../articleSchemaFields";
import {
  diffSchemas,
  summarizeDiff,
  type DiffField,
  type DiffRow,
} from "../schemaDiff";

const KIND_BADGE: Record<
  Exclude<DiffRow["kind"], "unchanged">,
  { label: string; variant: "success" | "danger" | "warning" }
> = {
  added: { label: "додано", variant: "success" },
  removed: { label: "вилучено", variant: "danger" },
  changed: { label: "змінено", variant: "warning" },
};

const FIELD_LABELS: Record<DiffField, string> = {
  role: "Роль",
  type: "Тип",
  options: "Значення переліку",
  repeatable: "Повторюване",
  required: "Обов'язкове",
};

function displayValue(field: DiffField, value: string | boolean): string {
  if (typeof value === "boolean") return value ? "так" : "ні";
  if (field === "role") {
    return value in ROLE_LABELS
      ? ROLE_LABELS[value as keyof typeof ROLE_LABELS]
      : value || "—";
  }
  if (field === "type") {
    return value in TYPE_LABELS
      ? TYPE_LABELS[value as keyof typeof TYPE_LABELS]
      : value || "—";
  }
  if (field === "options") {
    return value === "" ? "—" : String(value);
  }
  return String(value);
}

/** Field-by-field comparison of two article-schema `definition` values. */
export function SchemaDiffView({
  base,
  compare,
  baseLabel,
  compareLabel,
}: {
  base: unknown;
  compare: unknown;
  baseLabel: string;
  compareLabel: string;
}) {
  const [showUnchanged, setShowUnchanged] = useState(false);
  const rows = diffSchemas(base, compare);
  const summary = summarizeDiff(rows);
  const visible = rows.filter(
    (row) => showUnchanged || row.kind !== "unchanged",
  );

  const noChanges =
    summary.added === 0 && summary.removed === 0 && summary.changed === 0;

  return (
    <div className="grid gap-3">
      <p className="m-0 text-[0.85rem] text-muted-foreground">
        Порівняння: <strong>{baseLabel}</strong> → <strong>{compareLabel}</strong>
      </p>
      <div className="flex flex-wrap items-center gap-2 text-[0.82rem]">
        <Badge variant="success">+{summary.added} додано</Badge>
        <Badge variant="danger">−{summary.removed} вилучено</Badge>
        <Badge variant="warning">~{summary.changed} змінено</Badge>
        <label className="ml-2 inline-flex items-center gap-1.5">
          <input
            type="checkbox"
            checked={showUnchanged}
            onChange={(event) => setShowUnchanged(event.target.checked)}
          />
          показати незмінені ({summary.unchanged})
        </label>
      </div>

      {noChanges && !showUnchanged ? (
        <p className="lede">Ці версії мають однакові поля.</p>
      ) : (
        <ul className="m-0 grid list-none gap-1 p-0">
          {visible.map((row) => (
            <li
              key={row.path}
              className="rounded-md border border-border px-2 py-1.5 text-[0.85rem]"
              style={{ marginLeft: `${row.depth * 1}rem` }}
            >
              <span className="font-[650]">{row.path}</span>
              {row.kind !== "unchanged" && (
                <Badge
                  className="ml-2"
                  variant={KIND_BADGE[row.kind].variant}
                >
                  {KIND_BADGE[row.kind].label}
                </Badge>
              )}
              {row.changes.length > 0 && (
                <ul className="m-0 mt-1 grid list-none gap-0.5 p-0 text-[0.8rem] text-muted-foreground">
                  {row.changes.map((change) => (
                    <li key={change.field}>
                      {FIELD_LABELS[change.field]}:{" "}
                      <span className="line-through">
                        {displayValue(change.field, change.from)}
                      </span>{" "}
                      → {displayValue(change.field, change.to)}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
