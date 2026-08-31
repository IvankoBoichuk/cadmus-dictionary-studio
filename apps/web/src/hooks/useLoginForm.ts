import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import * as z from "zod";

import { API, apiMessageFrom } from "../api";
import { useAuth } from "../authContext";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const loginSchema = z.object({
  email: z
    .string()
    .trim()
    .min(1, "Email є обов’язковим полем.")
    .regex(EMAIL_RE, "Введіть коректну email-адресу."),
  password: z.string().min(1, "Пароль є обов’язковим полем."),
});

export type LoginValues = z.infer<typeof loginSchema>;

export function useLoginForm() {
  const navigate = useNavigate();
  const { setAuthenticated } = useAuth();

  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
    mode: "onTouched",
  });

  const onSubmit = form.handleSubmit(async (values) => {
    form.clearErrors("root");
    try {
      const user = await API.auth.login({
        email: values.email.trim(),
        password: values.password,
      });
      setAuthenticated(user);
      navigate("/dashboard", { replace: true });
    } catch (error) {
      form.setError("root", {
        message:
          apiMessageFrom(error) ??
          "Сервіс авторизації недоступний. Спробуйте пізніше.",
      });
    }
  });

  return { form, onSubmit };
}
