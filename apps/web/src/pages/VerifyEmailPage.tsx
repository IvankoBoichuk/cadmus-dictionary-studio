import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";

import { API } from "../api";

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

    const verificationToken = token;
    let active = true;
    async function verify() {
      try {
        const result = await API.auth.verifyEmail({ token: verificationToken });
        if (!active) return;
        if (result.ok) {
          setState({
            kind: "success",
            message:
              result.data.message ?? "Email підтверджено. Акаунт активовано.",
          });
        } else {
          setState({
            kind: "error",
            message:
              "message" in result.error
                ? result.error.message
                : "Не вдалося підтвердити email.",
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
