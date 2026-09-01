import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

import type { MemberResponse, Role } from "../api";
import type { MemberActionState } from "../hooks/useDictionaryMembers";
import { ASSIGNABLE_ROLE_OPTIONS, ROLE_LABELS } from "../roleLabels";
import { ProjectMemberRow } from "./ProjectMemberRow";

const COMPACT =
  "text-[0.82rem] [&_th]:px-2 [&_th]:py-1 [&_td]:px-2 [&_td]:py-1 [&_td]:align-middle";

/** BH-170: the project's members, with owner-only role/remove controls. */
export function ProjectMembersTable({
  members,
  myRole,
  actionState,
  onChangeRole,
  onRemove,
  onAdd,
}: {
  members: MemberResponse[];
  myRole: Role;
  actionState: Record<string, MemberActionState | undefined>;
  onChangeRole: (userId: string, role: Role) => void;
  onRemove: (member: MemberResponse) => void;
  onAdd: (email: string, role: Role) => Promise<boolean>;
}) {
  const canManage = myRole === "owner";
  const columns = canManage ? 3 : 2;
  const [adding, setAdding] = useState(false);

  return (
    <Table className={COMPACT}>
      <caption className="sr-only">Учасники проєкту</caption>
      <TableHeader>
        <TableRow>
          <TableHead scope="col">Пошта</TableHead>
          <TableHead scope="col">Роль</TableHead>
          {canManage && <TableHead scope="col">Дії</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {members.map((member) => {
          const rowState = actionState[member.user_id];
          const isOwner = member.role === "owner";
          return (
            <TableRow key={member.user_id}>
              <TableCell>{member.email}</TableCell>
              <TableCell>
                {canManage && !isOwner ? (
                  <>
                    <label
                      className="sr-only"
                      htmlFor={`member-role-${member.user_id}`}
                    >
                      Роль учасника {member.email}
                    </label>
                    <Select
                      value={member.role}
                      disabled={rowState?.pending}
                      onValueChange={(value) =>
                        onChangeRole(member.user_id, value as Role)
                      }
                    >
                      <SelectTrigger
                        id={`member-role-${member.user_id}`}
                        size="sm"
                        className="h-8 min-h-8! rounded-md px-2 py-0 text-[0.82rem]"
                      >
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
                  </>
                ) : (
                  ROLE_LABELS[member.role]
                )}
              </TableCell>
              {canManage && (
                <TableCell>
                  {!isOwner && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          variant="danger"
                          size="icon-sm"
                          type="button"
                          disabled={rowState?.pending}
                          onClick={() => onRemove(member)}
                          aria-label="Видалити"
                        >
                          <Trash2 aria-hidden="true" />
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        {rowState?.pending ? "Видаляємо…" : "Видалити"}
                      </TooltipContent>
                    </Tooltip>
                  )}
                  {rowState?.error && (
                    <p className="field-error" role="alert">
                      {rowState.error}
                    </p>
                  )}
                </TableCell>
              )}
            </TableRow>
          );
        })}

        {adding && (
          <ProjectMemberRow
            actionState={actionState.add}
            onAdd={onAdd}
            onDone={() => setAdding(false)}
          />
        )}
      </TableBody>
      {canManage && (
        <TableFooter>
          <TableRow>
            <TableCell colSpan={columns} className="text-center">
              {!adding && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      size="fab"
                      variant="secondary"
                      type="button"
                      onClick={() => setAdding(true)}
                      aria-label="Запросити учасника"
                    >
                      <Plus aria-hidden="true" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Запросити учасника</TooltipContent>
                </Tooltip>
              )}
            </TableCell>
          </TableRow>
        </TableFooter>
      )}
    </Table>
  );
}
