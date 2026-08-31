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
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { MemberResponse, Role } from "../api";
import type { MemberActionState } from "../hooks/useDictionaryMembers";
import { ASSIGNABLE_ROLE_OPTIONS, ROLE_LABELS } from "../roleLabels";

/** BH-170: the project's members, with owner-only role/remove controls. */
export function ProjectMembersTable({
  members,
  myRole,
  actionState,
  onChangeRole,
  onRemove,
}: {
  members: MemberResponse[];
  myRole: Role;
  actionState: Record<string, MemberActionState | undefined>;
  onChangeRole: (userId: string, role: Role) => void;
  onRemove: (member: MemberResponse) => void;
}) {
  const canManage = myRole === "owner";

  return (
    <Table>
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
                    <Button
                      variant="danger"
                      type="button"
                      disabled={rowState?.pending}
                      onClick={() => onRemove(member)}
                    >
                      {rowState?.pending ? "Видаляємо…" : "Видалити"}
                    </Button>
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
      </TableBody>
      </Table>
  );
}
