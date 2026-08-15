import { FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { API_BASE_URL } from "../config";

type RegistrationField = "email" | "password" | "password_confirmation";
type FieldErrors = Partial<Record<RegistrationField, string>>;

const MINIMUM_PASSWORD_LENGTH = 12;

function validate(
  email: string,
  password: string,
  confirmation: string,
): FieldErrors {
  const errors: FieldErrors = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
    errors.email = "Введіть коректну email-адресу.";
  }
  if (password.length < MINIMUM_PASSWORD_LENGTH) {
    errors.password = `Пароль має містити щонайменше ${MINIMUM_PASSWORD_LENGTH} символів.`;
  }
  if (password !== confirmation) {
    errors.password_confirmation = "Паролі не збігаються.";
  }
  return errors;
}

export function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [message, setMessage] = useState<string | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clientErrors = validate(email, password, confirmation);
    setErrors(clientErrors);
    setMessage(null);
    setSubmissionError(null);
    if (Object.keys(clientErrors).length > 0) return;

    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          password_confirmation: confirmation,
        }),
      });
      const payload = (await response.json()) as {
        errors?: FieldErrors;
        message?: string;
      };
      if (!response.ok) {
        if (payload.errors) setErrors(payload.errors);
        else setSubmissionError("Не вдалося створити акаунт. Спробуйте ще раз.");
        return;
      }
      setMessage(
        payload.message ??
          "Акаунт створено. Перевірте email, щоб активувати його.",
      );
    } catch {
      setSubmissionError("Сервіс реєстрації недоступний. Спробуйте пізніше.");
    } finally {
      setSubmitting(false);
    }
  }

  if (message) {
    return (
      <main className="auth-page" id="main-content">
        <section className="auth-card auth-card--result" aria-labelledby="page-title">
          <p className="eyebrow">Реєстрація завершена</p>
          <h1 id="page-title">Перевірте email</h1>
          <p className="result-message" role="status">
            {message}
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
        <form noValidate onSubmit={submit}>
          <div className="form-field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={email}
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? "email-error" : undefined}
              onChange={(event) => setEmail(event.target.value)}
            />
            {errors.email && (
              <p className="field-error" id="email-error">
                {errors.email}
              </p>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="password">Пароль</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="new-password"
              value={password}
              aria-invalid={Boolean(errors.password)}
              aria-describedby={errors.password ? "password-error" : undefined}
              onChange={(event) => setPassword(event.target.value)}
            />
            <p className="field-hint">Щонайменше 12 символів.</p>
            {errors.password && (
              <p className="field-error" id="password-error">
                {errors.password}
              </p>
            )}
          </div>
          <div className="form-field">
            <label htmlFor="password-confirmation">Підтвердження пароля</label>
            <input
              id="password-confirmation"
              name="password_confirmation"
              type="password"
              autoComplete="new-password"
              value={confirmation}
              aria-invalid={Boolean(errors.password_confirmation)}
              aria-describedby={
                errors.password_confirmation
                  ? "password-confirmation-error"
                  : undefined
              }
              onChange={(event) => setConfirmation(event.target.value)}
            />
            {errors.password_confirmation && (
              <p className="field-error" id="password-confirmation-error">
                {errors.password_confirmation}
              </p>
            )}
          </div>
          {submissionError && (
            <p className="form-error" role="alert">
              {submissionError}
            </p>
          )}
          <button disabled={submitting} type="submit">
            {submitting ? "Створюємо акаунт…" : "Створити акаунт"}
          </button>
        </form>
      </section>
    </main>
  );
}
