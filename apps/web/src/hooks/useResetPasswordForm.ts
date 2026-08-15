import { useFormik } from "formik";

import { API, apiMessageFrom, fieldErrorsFrom } from "../api";

export type ResetPasswordField = "new_password" | "new_password_confirmation";
type ResetPasswordValues = Record<ResetPasswordField, string>;
type FieldErrors = Partial<Record<ResetPasswordField, string>>;
type ResetPasswordStatus = {
  message?: string;
  tokenError?: string;
  submissionError?: string;
};

const MINIMUM_PASSWORD_LENGTH = 12;
const INITIAL_VALUES: ResetPasswordValues = {
  new_password: "",
  new_password_confirmation: "",
};

function validate(values: ResetPasswordValues): FieldErrors {
  const errors: FieldErrors = {};
  if (values.new_password.length < MINIMUM_PASSWORD_LENGTH) {
    errors.new_password = `Пароль має містити щонайменше ${MINIMUM_PASSWORD_LENGTH} символів.`;
  }
  if (values.new_password !== values.new_password_confirmation) {
    errors.new_password_confirmation = "Паролі не збігаються.";
  }
  return errors;
}

export function useResetPasswordForm(token: string) {
  const formik = useFormik<ResetPasswordValues>({
    initialValues: INITIAL_VALUES,
    validate,
    validateOnBlur: true,
    validateOnChange: true,
    onSubmit: async (values, helpers) => {
      helpers.setStatus(undefined);
      try {
        const response = await API.auth.resetPassword({
          token,
          new_password: values.new_password,
          new_password_confirmation: values.new_password_confirmation,
        });
        helpers.setStatus({
          message: response.message ?? "Пароль змінено. Тепер ви можете увійти.",
        });
      } catch (error) {
        const apiErrors = fieldErrorsFrom(error);
        if (apiErrors) {
          helpers.setErrors({
            new_password: apiErrors.password,
            new_password_confirmation: apiErrors.password_confirmation,
          });
          return;
        }
        const message = apiMessageFrom(error);
        if (message) {
          helpers.setStatus({ tokenError: message });
          return;
        }
        helpers.setStatus({
          submissionError: "Сервіс відновлення пароля недоступний. Спробуйте пізніше.",
        });
      }
    },
  });

  const status = formik.status as ResetPasswordStatus | undefined;
  return {
    ...formik,
    message: status?.message ?? null,
    tokenError: status?.tokenError ?? null,
    submissionError: status?.submissionError ?? null,
    submit: formik.handleSubmit,
    submitting: formik.isSubmitting,
  } as const;
}
