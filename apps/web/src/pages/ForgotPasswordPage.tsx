import { useRef } from "react";
import { Link } from "react-router-dom";

import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useForgotPasswordForm } from "../hooks/useForgotPasswordForm";

export function ForgotPasswordPage() {
  const form = useForgotPasswordForm();
  const formRef = useRef<HTMLFormElement>(null);

  useFocusFirstError(formRef, form.submitCount, form.isSubmitting);

  if (form.message) {
    return (
      <main className="auth-page" id="main-content">
        <section className="auth-card auth-card--result" aria-labelledby="page-title">
          <p className="eyebrow">Відновлення пароля</p>
          <h1 id="page-title">Перевірте email</h1>
          <p className="result-message" role="status">
            {form.message}
          </p>
          <Link to="/login">Повернутися до входу</Link>
        </section>
      </main>
    );
  }

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card" aria-labelledby="page-title">
        <p className="eyebrow">Відновлення пароля</p>
        <h1 id="page-title">Забули пароль?</h1>
        <p className="auth-intro">
          Вкажіть email, і ми надішлемо посилання для встановлення нового пароля.
        </p>
        <form noValidate ref={formRef} onSubmit={form.submit}>
          <div className="form-field">
            <label htmlFor="forgot-password-email">Email</label>
            <input
              id="forgot-password-email"
              type="email"
              autoComplete="email"
              spellCheck={false}
              {...form.getFieldProps("email")}
              aria-invalid={Boolean(form.errors.email)}
              aria-describedby={
                form.errors.email ? "forgot-password-email-error" : undefined
              }
            />
            {form.errors.email && (
              <p className="field-error" id="forgot-password-email-error">
                {form.errors.email}
              </p>
            )}
          </div>
          {form.submissionError && (
            <p className="form-error" role="alert">
              {form.submissionError}
            </p>
          )}
          <button disabled={form.submitting} type="submit">
            {form.submitting ? "Надсилаємо…" : "Надіслати інструкції"}
          </button>
        </form>
        <p className="auth-intro">
          <Link to="/login">Повернутися до входу</Link>
        </p>
      </section>
    </main>
  );
}
