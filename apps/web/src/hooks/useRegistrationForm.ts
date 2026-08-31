import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";

import { API, fieldErrorsFrom } from "../api";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MINIMUM_PASSWORD_LENGTH = 12;

export const REGISTRATION_FIELDS = [
  "email",
  "password",
  "password_confirmation",
] as const;
export type RegistrationField = (typeof REGISTRATION_FIELDS)[number];

const registrationSchema = z
  .object({
    email: z.string().trim().regex(EMAIL_RE, "Введіть коректну email-адресу."),
    password: z
      .string()
      .min(
        MINIMUM_PASSWORD_LENGTH,
        `Пароль має містити щонайменше ${MINIMUM_PASSWORD_LENGTH} символів.`,
      ),
    password_confirmation: z.string(),
  })
  .refine((values) => values.password === values.password_confirmation, {
    message: "Паролі не збігаються.",
    path: ["password_confirmation"],
  });

export type RegistrationValues = z.infer<typeof registrationSchema>;

export function useRegistrationForm() {
  const [message, setMessage] = useState<string | null>(null);

  const form = useForm<RegistrationValues>({
    resolver: zodResolver(registrationSchema),
    defaultValues: { email: "", password: "", password_confirmation: "" },
    mode: "onTouched",
  });

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    try {
      const response = await API.auth.register(values);
      setMessage(
        response.message ??
          "Акаунт створено. Перевірте email, щоб активувати його.",
      );
    } catch (error) {
      const apiErrors = fieldErrorsFrom(error);
      if (apiErrors) {
        for (const field of REGISTRATION_FIELDS) {
          if (apiErrors[field]) {
            form.setError(field, { message: apiErrors[field] });
          }
        }
        return;
      }
      form.setError("root", {
        message: "Сервіс реєстрації недоступний. Спробуйте пізніше.",
      });
    }
  });

  return { form, onSubmit, message };
}
