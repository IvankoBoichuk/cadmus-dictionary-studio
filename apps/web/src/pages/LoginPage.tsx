import { useRef } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";

import { API_BASE_URL } from "../config";
import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useLoginForm } from "../hooks/useLoginForm";
import { useAuth } from "../authContext";

function LoginForm({ sessionUnavailable }: { sessionUnavailable: boolean }) {
  const form = useLoginForm();
  const formRef = useRef<HTMLFormElement>(null);
  const [searchParams] = useSearchParams();

  useFocusFirstError(formRef, form.submitCount, form.isSubmitting);
  const googleAuthFailed = searchParams.get("error") === "google_auth_failed";
  const emailError = form.touched.email ? form.errors.email : undefined;
  const passwordError = form.touched.password ? form.errors.password : undefined;

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card" aria-labelledby="page-title">
        <p className="eyebrow">Робочий простір</p>
        <h1 id="page-title">Увійти</h1>
        <p className="auth-intro">
          Увійдіть за допомогою email і пароля, щоб продовжити роботу.
        </p>
        {sessionUnavailable && (
          <p className="form-error" role="alert">
            Не вдалося перевірити поточну сесію. Ви можете спробувати увійти.
          </p>
        )}
        {googleAuthFailed && (
          <p className="form-error" role="alert">
            Не вдалося увійти через Google. Спробуйте ще раз або скористайтеся
            email і паролем.
          </p>
        )}
        <form noValidate ref={formRef} onSubmit={form.handleSubmit}>
          <div className="form-field">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              spellCheck={false}
              {...form.getFieldProps("email")}
              aria-invalid={Boolean(emailError)}
              aria-describedby={emailError ? "login-email-error" : undefined}
            />
            {emailError && (
              <p className="field-error" id="login-email-error">
                {emailError}
              </p>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="login-password">Пароль</label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              {...form.getFieldProps("password")}
              aria-invalid={Boolean(passwordError)}
              aria-describedby={
                passwordError ? "login-password-error" : undefined
              }
            />
            {passwordError && (
              <p className="field-error" id="login-password-error">
                {passwordError}
              </p>
            )}
            <p className="field-hint">
              <Link to="/forgot-password">Забули пароль?</Link>
            </p>
          </div>
          {typeof form.status === "string" && (
            <p className="form-error" role="alert">
              {form.status}
            </p>
          )}
          <button disabled={form.isSubmitting} type="submit">
            {form.isSubmitting ? "Входимо…" : "Увійти"}
          </button>
        </form>
        <p className="oauth-divider">або</p>
        <a className="google-oauth-button" href={`${API_BASE_URL}/auth/google/start`}>
          Продовжити з Google
        </a>
      </section>
    </main>
  );
}

export function LoginPage() {
  const { session } = useAuth();
  if (session.status === "loading") {
    return (
      <main className="auth-page" id="main-content">
        <p role="status">Перевіряємо сесію…</p>
      </main>
    );
  }
  if (session.status === "authenticated") {
    return <Navigate replace to="/dashboard" />;
  }
  return <LoginForm sessionUnavailable={session.status === "unavailable"} />;
}
