import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";

import { API } from "../api";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const forgotPasswordSchema = z.object({
  email: z.string().trim().regex(EMAIL_RE, "Введіть коректну email-адресу."),
});

export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

export function useForgotPasswordForm() {
  const [message, setMessage] = useState<string | null>(null);

  const form = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
    mode: "onTouched",
  });

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    try {
      const response = await API.auth.forgotPassword(values);
      setMessage(
        response.message ??
          "Якщо такий email зареєстровано, ми надіслали інструкції для відновлення пароля.",
      );
    } catch {
      form.setError("root", {
        message: "Сервіс відновлення пароля недоступний. Спробуйте пізніше.",
      });
    }
  });

  return { form, onSubmit, message };
}
