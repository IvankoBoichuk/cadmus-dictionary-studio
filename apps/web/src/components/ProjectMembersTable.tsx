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
    <div className="table-wrapper">
      <table className="member-table">
        <caption className="visually-hidden">Учасники проєкту</caption>
        <thead>
          <tr>
            <th scope="col">Пошта</th>
            <th scope="col">Роль</th>
            {canManage && <th scope="col">Дії</th>}
          </tr>
        </thead>
        <tbody>
          {members.map((member) => {
            const rowState = actionState[member.user_id];
            const isOwner = member.role === "owner";
            return (
              <tr key={member.user_id}>
                <td>{member.email}</td>
                <td>
                  {canManage && !isOwner ? (
                    <>
                      <label
                        className="visually-hidden"
                        htmlFor={`member-role-${member.user_id}`}
                      >
                        Роль учасника {member.email}
                      </label>
                      <select
                        id={`member-role-${member.user_id}`}
                        value={member.role}
                        disabled={rowState?.pending}
                        onChange={(event) =>
                          onChangeRole(member.user_id, event.target.value as Role)
                        }
                      >
                        {ASSIGNABLE_ROLE_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    </>
                  ) : (
                    ROLE_LABELS[member.role]
                  )}
                </td>
                {canManage && (
                  <td>
                    {!isOwner && (
                      <button
                        type="button"
                        className="danger-button"
                        disabled={rowState?.pending}
                        onClick={() => onRemove(member)}
                      >
                        {rowState?.pending ? "Видаляємо…" : "Видалити"}
                      </button>
                    )}
                    {rowState?.error && (
                      <p className="field-error" role="alert">
                        {rowState.error}
                      </p>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
