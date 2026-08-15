import { Navigate } from "react-router-dom";

import { useLoginForm } from "../hooks/useLoginForm";
import { useAuth } from "../authContext";

function LoginForm({ sessionUnavailable }: { sessionUnavailable: boolean }) {
  const form = useLoginForm();
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
        <form noValidate onSubmit={form.handleSubmit}>
          <div className="form-field">
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
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
