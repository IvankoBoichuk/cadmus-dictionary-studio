import { Link, useLocation } from "react-router-dom";

import { useResetPasswordForm } from "../hooks/useResetPasswordForm";

function InvalidLinkResult({ message }: { message: string }) {
  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card auth-card--result" aria-labelledby="page-title">
        <p className="eyebrow">Відновлення пароля</p>
        <h1 id="page-title">Не вдалося відновити пароль</h1>
        <p className="result-message result-message--error" role="status">
          {message}
        </p>
        <Link to="/forgot-password">Надіслати новий запит</Link>
      </section>
    </main>
  );
}

export function ResetPasswordPage() {
  const location = useLocation();
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  const form = useResetPasswordForm(token ?? "");

  if (!token) {
    return (
      <InvalidLinkResult message="У посиланні немає токена для відновлення пароля." />
    );
  }

  if (form.message) {
    return (
      <main className="auth-page" id="main-content">
        <section className="auth-card auth-card--result" aria-labelledby="page-title">
          <p className="eyebrow">Відновлення пароля</p>
          <h1 id="page-title">Пароль змінено</h1>
          <p className="result-message" role="status">
            {form.message}
          </p>
          <Link to="/login">Увійти</Link>
        </section>
      </main>
    );
  }

  if (form.tokenError) {
    return <InvalidLinkResult message={form.tokenError} />;
  }

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card" aria-labelledby="page-title">
        <p className="eyebrow">Відновлення пароля</p>
        <h1 id="page-title">Встановіть новий пароль</h1>
        <p className="auth-intro">Введіть і підтвердіть новий пароль для акаунта.</p>
        <form noValidate onSubmit={form.submit}>
          <div className="form-field">
            <label htmlFor="reset-password-new-password">Новий пароль</label>
            <input
              id="reset-password-new-password"
              type="password"
              autoComplete="new-password"
              {...form.getFieldProps("new_password")}
              aria-invalid={Boolean(form.errors.new_password)}
              aria-describedby={
                form.errors.new_password
                  ? "reset-password-new-password-error"
                  : undefined
              }
            />
            <p className="field-hint">Щонайменше 12 символів.</p>
            {form.errors.new_password && (
              <p className="field-error" id="reset-password-new-password-error">
                {form.errors.new_password}
              </p>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="reset-password-new-password-confirmation">
              Підтвердження пароля
            </label>
            <input
              id="reset-password-new-password-confirmation"
              type="password"
              autoComplete="new-password"
              {...form.getFieldProps("new_password_confirmation")}
              aria-invalid={Boolean(form.errors.new_password_confirmation)}
              aria-describedby={
                form.errors.new_password_confirmation
                  ? "reset-password-new-password-confirmation-error"
                  : undefined
              }
            />
            {form.errors.new_password_confirmation && (
              <p
                className="field-error"
                id="reset-password-new-password-confirmation-error"
              >
                {form.errors.new_password_confirmation}
              </p>
            )}
          </div>
          {form.submissionError && (
            <p className="form-error" role="alert">
              {form.submissionError}
            </p>
          )}
          <button disabled={form.submitting} type="submit">
            {form.submitting ? "Змінюємо пароль…" : "Змінити пароль"}
          </button>
        </form>
      </section>
    </main>
  );
}
