import { Link, useLocation } from "react-router-dom";

import {
  useConfirmEmailChange,
  type ConfirmEmailChangeState,
} from "../hooks/useConfirmEmailChange";

const TITLES: Record<ConfirmEmailChangeState["kind"], string> = {
  loading: "Зачекайте",
  success: "Email оновлено",
  error: "Не вдалося змінити email",
};

const RESULT_TONE: Record<ConfirmEmailChangeState["kind"], string> = {
  loading: "text-muted-foreground",
  success: "text-success-foreground",
  error: "text-destructive",
};

export function ConfirmEmailChangePage() {
  const location = useLocation();
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  const state = useConfirmEmailChange(token);

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card text-center" aria-labelledby="page-title">
        <p className="eyebrow">Зміна email</p>
        <h1 id="page-title" className="mx-auto">
          {TITLES[state.kind]}
        </h1>
        <p
          className={`leading-relaxed ${RESULT_TONE[state.kind]}`}
          role="status"
        >
          {state.message}
        </p>
        {state.kind !== "loading" && <Link to="/login">Увійти</Link>}
      </section>
    </main>
  );
}
