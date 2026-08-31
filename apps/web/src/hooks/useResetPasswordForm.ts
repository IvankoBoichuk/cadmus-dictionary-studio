import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";

import { API, apiMessageFrom, fieldErrorsFrom } from "../api";

const MINIMUM_PASSWORD_LENGTH = 12;

const resetPasswordSchema = z
  .object({
    new_password: z
      .string()
      .min(
        MINIMUM_PASSWORD_LENGTH,
        `Пароль має містити щонайменше ${MINIMUM_PASSWORD_LENGTH} символів.`,
      ),
    new_password_confirmation: z.string(),
  })
  .refine(
    (values) => values.new_password === values.new_password_confirmation,
    {
      message: "Паролі не збігаються.",
      path: ["new_password_confirmation"],
    },
  );

export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;
export type ResetPasswordField = keyof ResetPasswordValues;

export function useResetPasswordForm(token: string) {
  const [message, setMessage] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);

  const form = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", new_password_confirmation: "" },
    mode: "onTouched",
  });

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    try {
      const response = await API.auth.resetPassword({
        token,
        new_password: values.new_password,
        new_password_confirmation: values.new_password_confirmation,
      });
      setMessage(response.message ?? "Пароль змінено. Тепер ви можете увійти.");
    } catch (error) {
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors) {
        if (apiErrors.password) {
          form.setError("new_password", { message: apiErrors.password });
        }
        if (apiErrors.password_confirmation) {
          form.setError("new_password_confirmation", {
            message: apiErrors.password_confirmation,
          });
        }
        return;
      }
      const apiMessage = apiMessageFrom(error);
      if (apiMessage) {
        setTokenError(apiMessage);
        return;
      }
      form.setError("root", {
        message: "Сервіс відновлення пароля недоступний. Спробуйте пізніше.",
      });
    }
  });

  return { form, onSubmit, message, tokenError };
}
