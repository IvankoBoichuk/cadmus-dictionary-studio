import { Link, useLocation } from "react-router-dom";

import {
  useEmailVerification,
  type VerificationState,
} from "../hooks/useEmailVerification";

const TITLES: Record<VerificationState["kind"], string> = {
  loading: "Зачекайте",
  success: "Акаунт активовано",
  error: "Не вдалося активувати акаунт",
};

export function VerifyEmailPage() {
  const location = useLocation();
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  const state = useEmailVerification(token);

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card auth-card--result" aria-labelledby="page-title">
        <p className="eyebrow">Підтвердження email</p>
        <h1 id="page-title">{TITLES[state.kind]}</h1>
        <p
          className={`result-message result-message--${state.kind}`}
          role="status"
        >
          {state.message}
        </p>
        {state.kind !== "loading" && <Link to="/">Повернутися на головну</Link>}
      </section>
    </main>
  );
}
