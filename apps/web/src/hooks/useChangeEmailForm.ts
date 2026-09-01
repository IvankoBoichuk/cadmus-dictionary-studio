import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";

import { API, ApiError, apiMessageFrom, fieldErrorsFrom } from "../api";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const changeEmailSchema = z.object({
  new_email: z
    .string()
    .trim()
    .min(1, "Введіть нову email-адресу.")
    .regex(EMAIL_RE, "Введіть коректну email-адресу."),
  current_password: z.string().min(1, "Введіть поточний пароль."),
});

export type ChangeEmailValues = z.infer<typeof changeEmailSchema>;

export function useChangeEmailForm() {
  const [message, setMessage] = useState<string | null>(null);

  const form = useForm<ChangeEmailValues>({
    resolver: zodResolver(changeEmailSchema),
    defaultValues: { new_email: "", current_password: "" },
    mode: "onTouched",
  });

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    setMessage(null);
    try {
      const response = await API.auth.changeEmail({
        new_email: values.new_email.trim(),
        current_password: values.current_password,
      });
      form.reset();
      setMessage(
        response.message ??
          "Ми надіслали лист на нову адресу — відкрийте посилання з нього, щоб підтвердити зміну.",
      );
    } catch (error) {
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors?.new_email) {
        form.setError("new_email", { message: apiErrors.new_email });
        return;
      }
      if (error instanceof ApiError && error.status === 403) {
        form.setError("current_password", {
          message: apiMessageFrom(error) ?? "Поточний пароль неправильний.",
        });
        return;
      }
      form.setError("root", {
        message:
          apiMessageFrom(error) ??
          "Не вдалося змінити email. Спробуйте пізніше.",
      });
    }
  });

  return { form, onSubmit, message };
}
