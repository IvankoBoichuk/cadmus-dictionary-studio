import { useRef } from "react";
import { Link } from "react-router-dom";

import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useRegistrationForm } from "../hooks/useRegistrationForm";

export function RegisterPage() {
  const form = useRegistrationForm();
  const formRef = useRef<HTMLFormElement>(null);

  useFocusFirstError(formRef, form.submitCount, form.isSubmitting);

  if (form.message) {
    return (
      <main className="auth-page" id="main-content">
        <section className="auth-card auth-card--result" aria-labelledby="page-title">
          <p className="eyebrow">Реєстрація завершена</p>
          <h1 id="page-title">Перевірте email</h1>
          <p className="result-message" role="status">
            {form.message}
          </p>
          <Link to="/">Повернутися на головну</Link>
        </section>
      </main>
    );
  }

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card" aria-labelledby="page-title">
        <p className="eyebrow">Новий акаунт</p>
        <h1 id="page-title">Зареєструватися</h1>
        <p className="auth-intro">
          Створіть акаунт за допомогою email і пароля. Після цього ми надішлемо
          посилання для підтвердження.
        </p>
        <form noValidate ref={formRef} onSubmit={form.submit}>
          <div className="form-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              spellCheck={false}
              {...form.getFieldProps("email")}
              aria-invalid={Boolean(form.errors.email)}
              aria-describedby={form.errors.email ? "email-error" : undefined}
            />
            {form.errors.email && (
              <p className="field-error" id="email-error">
                {form.errors.email}
              </p>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              type="password"
              autoComplete="new-password"
              {...form.getFieldProps("password")}
              aria-invalid={Boolean(form.errors.password)}
              aria-describedby={form.errors.password ? "password-error" : undefined}
            />
            <p className="field-hint">Щонайменше 12 символів.</p>
            {form.errors.password && (
              <p className="field-error" id="password-error">
                {form.errors.password}
              </p>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="password-confirmation">Підтвердження пароля</label>
            <input
              id="password-confirmation"
              type="password"
              autoComplete="new-password"
              {...form.getFieldProps("password_confirmation")}
              aria-invalid={Boolean(form.errors.password_confirmation)}
              aria-describedby={
                form.errors.password_confirmation
                  ? "password-confirmation-error"
                  : undefined
              }
            />
            {form.errors.password_confirmation && (
              <p className="field-error" id="password-confirmation-error">
                {form.errors.password_confirmation}
              </p>
            )}
          </div>
          {form.submissionError && (
            <p className="form-error" role="alert">
              {form.submissionError}
            </p>
          )}
          <button disabled={form.submitting} type="submit">
            {form.submitting ? "Створюємо акаунт…" : "Створити акаунт"}
          </button>
        </form>
      </section>
    </main>
  );
}
