import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { API_BASE_URL } from "../config";

type VerificationState =
  | { kind: "loading"; message: string }
  | { kind: "success"; message: string }
  | { kind: "error"; message: string };

export function VerifyEmailPage() {
  const location = useLocation();
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  const [state, setState] = useState<VerificationState>(() =>
    token
      ? { kind: "loading", message: "Підтверджуємо email…" }
      : {
          kind: "error",
          message: "У посиланні немає токена підтвердження.",
        },
  );

  useEffect(() => {
    if (!token) {
      return;
    }

    let active = true;
    async function verify() {
      try {
        const response = await fetch(`${API_BASE_URL}/auth/verify-email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        });
        const payload = (await response.json()) as { message?: string };
        if (!active) return;
        if (response.ok) {
          setState({
            kind: "success",
            message: payload.message ?? "Email підтверджено. Акаунт активовано.",
          });
        } else {
          setState({
            kind: "error",
            message: payload.message ?? "Не вдалося підтвердити email.",
          });
        }
      } catch {
        if (active) {
          setState({
            kind: "error",
            message: "Сервіс підтвердження недоступний. Спробуйте пізніше.",
          });
        }
      }
    }
    void verify();
    return () => {
      active = false;
    };
  }, [token]);

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card auth-card--result" aria-labelledby="page-title">
        <p className="eyebrow">Підтвердження email</p>
        <h1 id="page-title">
          {state.kind === "loading"
            ? "Зачекайте"
            : state.kind === "success"
              ? "Акаунт активовано"
              : "Не вдалося активувати акаунт"}
        </h1>
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
