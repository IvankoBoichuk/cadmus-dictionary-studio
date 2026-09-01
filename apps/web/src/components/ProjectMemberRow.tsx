import { Check, X } from "lucide-react";
import { type KeyboardEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TableCell, TableRow } from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import type { Role } from "../api";
import type { MemberActionState } from "../hooks/useDictionaryMembers";
import { ASSIGNABLE_ROLE_OPTIONS } from "../roleLabels";

const CELL_INPUT = "h-8 min-h-8 rounded-md px-2 py-1 text-[0.82rem]";
const CELL_TRIGGER = "h-8 min-h-8! rounded-md px-2 py-0 text-[0.82rem]";

/** The "Запросити учасника" form rendered inline as a table row (one field per
 * column) — replaces the standalone `ProjectMemberForm`. */
export function ProjectMemberRow({
  actionState,
  onAdd,
  onDone,
}: {
  actionState: MemberActionState | undefined;
  onAdd: (email: string, role: Role) => Promise<boolean>;
  onDone: () => void;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("viewer");

  const submit = () => {
    if (!email.trim()) return;
    void onAdd(email.trim(), role).then((added) => {
      if (added) onDone();
    });
  };

  const onEnter = (event: KeyboardEvent) => {
    if (event.key === "Enter") {
      event.preventDefault();
      submit();
    }
  };

  return (
    <>
      <TableRow className="bg-accent/40">
        <TableCell>
          <Input
            className={CELL_INPUT}
            aria-label="Пошта"
            type="email"
            autoComplete="off"
            spellCheck={false}
            placeholder="user@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            onKeyDown={onEnter}
          />
        </TableCell>
        <TableCell>
          <Select value={role} onValueChange={(value) => setRole(value as Role)}>
            <SelectTrigger size="sm" className={CELL_TRIGGER} aria-label="Роль">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ASSIGNABLE_ROLE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </TableCell>
        <TableCell>
          <div className="flex gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon-sm"
                  type="button"
                  disabled={actionState?.pending || !email.trim()}
                  onClick={submit}
                  aria-label="Запросити"
                >
                  <Check aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {actionState?.pending ? "Запрошуємо…" : "Запросити"}
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  size="icon-sm"
                  variant="secondary"
                  type="button"
                  onClick={onDone}
                  aria-label="Скасувати"
                >
                  <X aria-hidden="true" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Скасувати</TooltipContent>
            </Tooltip>
          </div>
        </TableCell>
      </TableRow>
      {actionState?.error && (
        <TableRow className="bg-accent/40">
          <TableCell colSpan={3}>
            <p className="field-error m-0" role="alert">
              {actionState.error}
            </p>
          </TableCell>
        </TableRow>
      )}
    </>
  );
}
