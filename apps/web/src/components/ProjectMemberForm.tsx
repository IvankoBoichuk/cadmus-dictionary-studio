import { useState, type FormEvent } from "react";

import type { Role } from "../api";
import type { MemberActionState } from "../hooks/useDictionaryMembers";
import { ASSIGNABLE_ROLE_OPTIONS } from "../roleLabels";

/** BH-170: invites a registered user to a project by email. */
export function ProjectMemberForm({
  actionState,
  onAdd,
}: {
  actionState: MemberActionState | undefined;
  onAdd: (email: string, role: Role) => Promise<boolean>;
}) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("viewer");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    if (!email.trim()) return;
    void onAdd(email.trim(), role).then((added) => {
      if (added) setEmail("");
    });
  };

  return (
    <form
      noValidate
      onSubmit={handleSubmit}
      aria-labelledby="member-form-heading"
      className="form-section"
    >
      <h2 id="member-form-heading">Запросити учасника</h2>

      <div className="form-field">
        <label htmlFor="member-email">Пошта</label>
        <input
          id="member-email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>

      <div className="form-field">
        <label htmlFor="member-role">Роль</label>
        <select
          id="member-role"
          value={role}
          onChange={(event) => setRole(event.target.value as Role)}
        >
          {ASSIGNABLE_ROLE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      {actionState?.error && (
        <p className="form-error" role="alert">
          {actionState.error}
        </p>
      )}

      <div className="form-actions">
        <button disabled={actionState?.pending} type="submit">
          {actionState?.pending ? "Запрошуємо…" : "Запросити"}
        </button>
      </div>
    </form>
  );
}
