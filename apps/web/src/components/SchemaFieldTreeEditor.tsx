import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import {
  MAX_SCHEMA_DEPTH,
  ROLE_OPTIONS,
  TYPE_OPTIONS,
} from "../articleSchemaFields";
import type {
  NodePath,
  useArticleSchemaEditor,
} from "../hooks/useArticleSchemaEditor";
import type { SchemaNode } from "../schemaDiff";
import { nodePathKey } from "../schemaValidation";

type Editor = ReturnType<typeof useArticleSchemaEditor>;

const CELL_INPUT = "h-8 min-h-8 rounded-md px-2 py-1 text-[0.82rem]";
const CELL_TRIGGER = "h-8 min-h-8! rounded-md px-2 py-0 text-[0.82rem]";

function NodeRow({
  node,
  path,
  depth,
  siblingCount,
  editor,
}: {
  node: SchemaNode;
  path: NodePath;
  depth: number;
  siblingCount: number;
  editor: Editor;
}) {
  const key = nodePathKey(path);
  const index = path[path.length - 1];
  const err = editor.errors;

  return (
    <div className="grid gap-2 rounded-md border border-border p-2">
      <div className="flex flex-wrap items-start gap-2">
        <div className="grid min-w-[10rem] flex-1 gap-1">
          <Input
            className={CELL_INPUT}
            aria-label={`Назва поля (рівень ${depth})`}
            placeholder="назва поля"
            value={node.name}
            onChange={(event) => {
              editor.updateNode(path, { name: event.target.value });
              editor.clearError(`${key}.name`);
            }}
          />
          {err[`${key}.name`] && (
            <span className="field-error">{err[`${key}.name`]}</span>
          )}
        </div>

        <div className="grid gap-1">
          <Select
            value={node.role}
            onValueChange={(value) => {
              editor.updateNode(path, { role: value });
              editor.clearError(`${key}.role`);
            }}
          >
            <SelectTrigger
              size="sm"
              className={CELL_TRIGGER}
              aria-label={`Роль поля (рівень ${depth})`}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ROLE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {err[`${key}.role`] && (
            <span className="field-error">{err[`${key}.role`]}</span>
          )}
        </div>

        <div className="grid gap-1">
          <Select
            value={node.type}
            onValueChange={(value) => {
              editor.updateNode(path, {
                type: value as SchemaNode["type"],
              });
              editor.clearError(`${key}.type`);
            }}
          >
            <SelectTrigger
              size="sm"
              className={CELL_TRIGGER}
              aria-label={`Тип поля (рівень ${depth})`}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TYPE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {err[`${key}.type`] && (
            <span className="field-error">{err[`${key}.type`]}</span>
          )}
        </div>

        <label className="flex items-center gap-1.5 text-[0.82rem]">
          <Checkbox
            checked={node.repeatable}
            onCheckedChange={(checked) =>
              editor.updateNode(path, { repeatable: checked === true })
            }
          />
          повторюване
        </label>
        <label className="flex items-center gap-1.5 text-[0.82rem]">
          <Checkbox
            checked={node.required}
            onCheckedChange={(checked) =>
              editor.updateNode(path, { required: checked === true })
            }
          />
          обов'язкове
        </label>

        <div className="ml-auto flex gap-1">
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon-sm"
                variant="secondary"
                type="button"
                disabled={index === 0}
                onClick={() => editor.moveNode(path, -1)}
                aria-label="Пересунути вище"
              >
                <ArrowUp aria-hidden="true" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Вище</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon-sm"
                variant="secondary"
                type="button"
                disabled={index === siblingCount - 1}
                onClick={() => editor.moveNode(path, 1)}
                aria-label="Пересунути нижче"
              >
                <ArrowDown aria-hidden="true" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Нижче</TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                size="icon-sm"
                variant="danger"
                type="button"
                onClick={() => editor.removeNode(path)}
                aria-label="Видалити поле"
              >
                <Trash2 aria-hidden="true" />
              </Button>
            </TooltipTrigger>
            <TooltipContent>Видалити</TooltipContent>
          </Tooltip>
        </div>
      </div>

      {node.type === "enum" && (
        <div className="grid gap-1.5 border-l border-border pl-3">
          <span className="text-[0.78rem] text-muted-foreground">
            Значення переліку
          </span>
          {node.options.map((option, optionIndex) => (
            <div key={optionIndex} className="flex items-center gap-1.5">
              <Input
                className={`${CELL_INPUT} max-w-[16rem]`}
                aria-label={`Значення переліку ${optionIndex + 1} (${
                  node.name || "поле"
                })`}
                placeholder="значення"
                value={option}
                onChange={(event) => {
                  const next = [...node.options];
                  next[optionIndex] = event.target.value;
                  editor.updateNode(path, { options: next });
                  editor.clearError(`${key}.options`);
                }}
              />
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    size="icon-sm"
                    variant="danger"
                    type="button"
                    aria-label={`Видалити значення ${optionIndex + 1}`}
                    onClick={() => {
                      editor.updateNode(path, {
                        options: node.options.filter(
                          (_, i) => i !== optionIndex,
                        ),
                      });
                      editor.clearError(`${key}.options`);
                    }}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Видалити</TooltipContent>
              </Tooltip>
            </div>
          ))}
          <div>
            <Button
              size="sm"
              variant="secondary"
              type="button"
              onClick={() => {
                editor.updateNode(path, { options: [...node.options, ""] });
                editor.clearError(`${key}.options`);
              }}
            >
              <Plus aria-hidden="true" />
              Додати значення
            </Button>
          </div>
          {err[`${key}.options`] && (
            <span className="field-error">{err[`${key}.options`]}</span>
          )}
        </div>
      )}

      {err[`${key}.children`] && (
        <span className="field-error">{err[`${key}.children`]}</span>
      )}

      {(node.children.length > 0 || depth < MAX_SCHEMA_DEPTH) && (
        <div className="grid gap-2 border-l border-border pl-3">
          <NodeList
            nodes={node.children}
            parentPath={path}
            depth={depth + 1}
            editor={editor}
          />
          {depth < MAX_SCHEMA_DEPTH && (
            <div>
              <Button
                size="sm"
                variant="secondary"
                type="button"
                onClick={() => editor.appendChild(path)}
              >
                <Plus aria-hidden="true" />
                Додати підполе
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function NodeList({
  nodes,
  parentPath,
  depth,
  editor,
}: {
  nodes: SchemaNode[];
  parentPath: NodePath;
  depth: number;
  editor: Editor;
}) {
  return (
    <div className="grid gap-2">
      {nodes.map((node, index) => (
        <NodeRow
          key={`${parentPath.join("-")}-${index}`}
          node={node}
          path={[...parentPath, index]}
          depth={depth}
          siblingCount={nodes.length}
          editor={editor}
        />
      ))}
    </div>
  );
}

/** Structured tree editor over an article-schema `definition`. */
export function SchemaFieldTreeEditor({ editor }: { editor: Editor }) {
  return (
    <div className="grid gap-3">
      {editor.fields.length === 0 && (
        <p className="lede">
          Полів ще немає. Додайте перше поле верхнього рівня.
        </p>
      )}
      <NodeList
        nodes={editor.fields}
        parentPath={[]}
        depth={1}
        editor={editor}
      />
      <div>
        <Button
          size="sm"
          variant="secondary"
          type="button"
          onClick={() => editor.appendChild([])}
        >
          <Plus aria-hidden="true" />
          Додати поле
        </Button>
      </div>
      {editor.errors.fields && (
        <p className="field-error" role="alert">
          {editor.errors.fields}
        </p>
      )}
    </div>
  );
}
