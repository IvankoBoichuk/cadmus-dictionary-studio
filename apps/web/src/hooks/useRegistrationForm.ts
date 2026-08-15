import { useFormik } from "formik";

import { API, fieldErrorsFrom } from "../api";

export type RegistrationField = "email" | "password" | "password_confirmation";
type RegistrationValues = Record<RegistrationField, string>;
type FieldErrors = Partial<Record<RegistrationField, string>>;
type RegistrationStatus = {
  message?: string;
  submissionError?: string;
};

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
  const formik = useFormik<RegistrationValues>({
    initialValues: INITIAL_VALUES,
    validate,
    validateOnBlur: true,
    validateOnChange: true,
    onSubmit: async (values, helpers) => {
      helpers.setStatus(undefined);
      try {
        const response = await API.auth.register(values);
        helpers.setStatus({
          message:
            response.message ??
            "Акаунт створено. Перевірте email, щоб активувати його.",
        });
      } catch (error) {
        const apiErrors = fieldErrorsFrom(error);
        if (apiErrors) {
          helpers.setErrors({
            email: apiErrors.email,
            password: apiErrors.password,
            password_confirmation: apiErrors.password_confirmation,
          });
          return;
        }
        helpers.setStatus({
          submissionError: "Сервіс реєстрації недоступний. Спробуйте пізніше.",
        });
      }
    },
  });

  const status = formik.status as RegistrationStatus | undefined;
  return {
    ...formik,
    message: status?.message ?? null,
    submissionError: status?.submissionError ?? null,
    submit: formik.handleSubmit,
    submitting: formik.isSubmitting,
  } as const;
}
