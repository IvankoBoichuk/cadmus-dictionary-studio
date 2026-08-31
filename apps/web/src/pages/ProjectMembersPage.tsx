import { Navigate, useParams } from "react-router-dom";

import type { MemberResponse } from "../api";
import { ProjectMemberForm } from "../components/ProjectMemberForm";
import { ProjectMembersTable } from "../components/ProjectMembersTable";
import { useDictionaryMembers } from "../hooks/useDictionaryMembers";

function ProjectMembersWorkspace({ dictionaryId }: { dictionaryId: string }) {
  const { state, actionState, add, changeRole, remove } =
    useDictionaryMembers(dictionaryId);

  const handleRemove = (member: MemberResponse) => {
    if (window.confirm(`Прибрати «${member.email}» з проєкту?`)) {
      void remove(member.user_id);
    }
  };

  return (
    <>
      {state.status === "loading" && (
        <p role="status">Завантажуємо учасників…</p>
      )}
      {state.status === "error" && (
        <p className="form-error" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "loaded" && (
        <>
          <div className="form-section">
            <h2>Список учасників</h2>
            <ProjectMembersTable
              members={state.members}
              myRole={state.myRole}
              actionState={actionState}
              onChangeRole={(userId, role) => void changeRole(userId, role)}
              onRemove={handleRemove}
            />
          </div>
          {state.myRole === "owner" && (
            <ProjectMemberForm actionState={actionState.add} onAdd={add} />
          )}
        </>
      )}
    </>
  );
}

export function ProjectMembersPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return (
    <>
      <h2 className="mb-2 text-[1.15rem]">Учасники проєкту</h2>
      <p className="max-w-[60ch] text-[0.9rem] text-muted-foreground">
        Керуйте тим, хто має доступ до словника, і якою є їхня роль.
      </p>
      <div className="dictionary-form">
        <ProjectMembersWorkspace dictionaryId={dictionaryId} />
      </div>
    </>
  );
}
