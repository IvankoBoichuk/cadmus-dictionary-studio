import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";

import { API, ApiError, apiMessageFrom, fieldErrorsFrom } from "../api";

const MINIMUM_PASSWORD_LENGTH = 12;

const changePasswordSchema = z
  .object({
    current_password: z.string().min(1, "Введіть поточний пароль."),
    new_password: z
      .string()
      .min(
        MINIMUM_PASSWORD_LENGTH,
        `Пароль має містити щонайменше ${MINIMUM_PASSWORD_LENGTH} символів.`,
      ),
    new_password_confirmation: z.string(),
  })
  .refine((values) => values.new_password === values.new_password_confirmation, {
    message: "Паролі не збігаються.",
    path: ["new_password_confirmation"],
  });

export type ChangePasswordValues = z.infer<typeof changePasswordSchema>;

export function useChangePasswordForm() {
  const [message, setMessage] = useState<string | null>(null);

  const form = useForm<ChangePasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      new_password_confirmation: "",
    },
    mode: "onTouched",
  });

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    setMessage(null);
    try {
      const response = await API.auth.changePassword(values);
      form.reset();
      setMessage(
        response.message ??
          "Пароль змінено. Інші пристрої вийшли із системи.",
      );
    } catch (error) {
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors) {
        for (const [field, msg] of Object.entries(apiErrors)) {
          if (field === "password") {
            form.setError("new_password", { message: msg });
          } else if (field === "password_confirmation") {
            form.setError("new_password_confirmation", { message: msg });
          }
        }
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
          "Не вдалося змінити пароль. Спробуйте пізніше.",
      });
    }
  });

  return { form, onSubmit, message };
}
