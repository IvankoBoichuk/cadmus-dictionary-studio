import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

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
        <Label htmlFor="member-email">Пошта</Label>
        <Input
          id="member-email"
          name="email"
          type="email"
          autoComplete="off"
          spellCheck={false}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
      </div>

      <div className="form-field">
        <Label htmlFor="member-role">Роль</Label>
        <Select value={role} onValueChange={(value) => setRole(value as Role)}>
          <SelectTrigger id="member-role">
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
      </div>

      {actionState?.error && (
        <p className="form-error" role="alert">
          {actionState.error}
        </p>
      )}

      <div className="form-actions">
        <Button disabled={actionState?.pending} type="submit">
          {actionState?.pending ? "Запрошуємо…" : "Запросити"}
        </Button>
      </div>
    </form>
  );
}
