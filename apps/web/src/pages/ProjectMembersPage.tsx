import { Navigate, useParams } from "react-router-dom";

import type { MemberResponse } from "../api";
import { useAuth } from "../authContext";
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
  const { session } = useAuth();
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (session.status === "loading") {
    return (
      <main className="page" id="main-content">
        <p role="status">Завантажуємо робочий простір…</p>
      </main>
    );
  }
  if (session.status !== "authenticated") {
    return <Navigate replace to="/login" />;
  }
  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return (
    <main className="page" id="main-content">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Словник</p>
        <h1 id="page-title">Учасники проєкту</h1>
        <p className="lede">
          Керуйте тим, хто має доступ до словника, і якою є їхня роль.
        </p>
      </section>
      <div className="dictionary-form">
        <ProjectMembersWorkspace dictionaryId={dictionaryId} />
      </div>
    </main>
  );
}
