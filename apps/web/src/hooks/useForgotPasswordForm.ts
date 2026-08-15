import { useFormik } from "formik";

import { API } from "../api";

type ForgotPasswordValues = { email: string };
type FieldErrors = Partial<Record<"email", string>>;
type ForgotPasswordStatus = {
  message?: string;
  submissionError?: string;
};

const INITIAL_VALUES: ForgotPasswordValues = { email: "" };

function validate(values: ForgotPasswordValues): FieldErrors {
  const errors: FieldErrors = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim())) {
    errors.email = "Введіть коректну email-адресу.";
  }
  return errors;
}

export function useForgotPasswordForm() {
  const formik = useFormik<ForgotPasswordValues>({
    initialValues: INITIAL_VALUES,
    validate,
    validateOnBlur: true,
    validateOnChange: true,
    onSubmit: async (values, helpers) => {
      helpers.setStatus(undefined);
      try {
        const response = await API.auth.forgotPassword(values);
        helpers.setStatus({
          message:
            response.message ??
            "Якщо такий email зареєстровано, ми надіслали інструкції для відновлення пароля.",
        });
      } catch {
        helpers.setStatus({
          submissionError: "Сервіс відновлення пароля недоступний. Спробуйте пізніше.",
        });
      }
    },
  });

  const status = formik.status as ForgotPasswordStatus | undefined;
  return {
    ...formik,
    message: status?.message ?? null,
    submissionError: status?.submissionError ?? null,
    submit: formik.handleSubmit,
    submitting: formik.isSubmitting,
  } as const;
}
