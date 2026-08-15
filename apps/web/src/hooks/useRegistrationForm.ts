import { useState, type ChangeEvent, type FormEvent } from "react";

import { API, fieldErrorsFrom } from "../api";

export type RegistrationField = "email" | "password" | "password_confirmation";
type RegistrationValues = Record<RegistrationField, string>;
type FieldErrors = Partial<Record<RegistrationField, string>>;

const MINIMUM_PASSWORD_LENGTH = 12;
const INITIAL_VALUES: RegistrationValues = {
  email: "",
  password: "",
  password_confirmation: "",
};

function validate(values: RegistrationValues): FieldErrors {
  const errors: FieldErrors = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
    errors.email = "Введіть коректну email-адресу.";
  }
  if (values.password.length < MINIMUM_PASSWORD_LENGTH) {
    errors.password = `Пароль має містити щонайменше ${MINIMUM_PASSWORD_LENGTH} символів.`;
  }
  if (values.password !== values.password_confirmation) {
    errors.password_confirmation = "Паролі не збігаються.";
  }
  return errors;
}

export function useRegistrationForm() {
  const [values, setValues] = useState<RegistrationValues>(INITIAL_VALUES);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [message, setMessage] = useState<string | null>(null);
  const [submissionError, setSubmissionError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function getFieldProps(field: RegistrationField) {
    return {
      name: field,
      value: values[field],
      onChange(event: ChangeEvent<HTMLInputElement>) {
        setValues((current) => ({ ...current, [field]: event.target.value }));
      },
    };
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clientErrors = validate(values);
    setErrors(clientErrors);
    setMessage(null);
    setSubmissionError(null);
    if (Object.keys(clientErrors).length > 0) return;

    setSubmitting(true);
    try {
      const response = await API.auth.register(values);
      setMessage(
        response.message ??
          "Акаунт створено. Перевірте email, щоб активувати його.",
      );
    } catch (error) {
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors) {
        setErrors({
          email: apiErrors.email,
          password: apiErrors.password,
          password_confirmation: apiErrors.password_confirmation,
        });
      } else {
        setSubmissionError("Сервіс реєстрації недоступний. Спробуйте пізніше.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return {
    errors,
    getFieldProps,
    message,
    submissionError,
    submit,
    submitting,
  } as const;
}
