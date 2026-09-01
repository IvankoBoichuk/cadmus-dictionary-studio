import { Badge } from "@/components/ui/badge";

import { ROLE_LABELS, TYPE_LABELS } from "../articleSchemaFields";
import { parseSchemaFields, type SchemaNode } from "../schemaDiff";

function roleLabel(role: string): string {
  return role in ROLE_LABELS
    ? ROLE_LABELS[role as keyof typeof ROLE_LABELS]
    : role || "—";
}

function typeLabel(type: string): string {
  return type in TYPE_LABELS
    ? TYPE_LABELS[type as keyof typeof TYPE_LABELS]
    : type || "—";
}

function NodeList({ nodes }: { nodes: SchemaNode[] }) {
  if (nodes.length === 0) return null;
  return (
    <ul className="my-2 grid list-disc gap-1 pl-5">
      {nodes.map((node, index) => (
        <li key={`${node.name}-${index}`}>
          <span className="font-[650]">{node.name || "(без назви)"}</span>
          <Badge className="ml-2" variant="secondary">
            {roleLabel(node.role)}
          </Badge>
          <Badge className="ml-2" variant="info">
            {typeLabel(node.type)}
          </Badge>
          {node.type === "enum" && node.options.length > 0 && (
            <span className="ml-2 inline-flex flex-wrap gap-1 align-middle">
              {node.options.map((option, optionIndex) => (
                <Badge key={`${option}-${optionIndex}`} variant="secondary">
                  {option}
                </Badge>
              ))}
            </span>
          )}
          {node.repeatable && (
            <Badge className="ml-2" variant="warning">
              повторюване
            </Badge>
          )}
          {node.required && (
            <Badge className="ml-2" variant="warning">
              обов'язкове
            </Badge>
          )}
          <NodeList nodes={node.children} />
        </li>
      ))}
    </ul>
  );
}

/** Read-only view of a stored article-schema `definition` field tree. */
export function SchemaFieldTree({ definition }: { definition: unknown }) {
  const fields = parseSchemaFields(definition);
  if (fields.length === 0) {
    return <p className="lede">Ця версія не містить полів.</p>;
  }
  return <NodeList nodes={fields} />;
}
