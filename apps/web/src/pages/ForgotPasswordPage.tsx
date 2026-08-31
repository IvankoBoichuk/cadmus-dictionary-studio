import { useRef } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useForgotPasswordForm } from "../hooks/useForgotPasswordForm";

export function ForgotPasswordPage() {
  const { form, onSubmit, message } = useForgotPasswordForm();
  const formRef = useRef<HTMLFormElement>(null);

  useFocusFirstError(
    formRef,
    form.formState.submitCount,
    form.formState.isSubmitting,
  );

  if (message) {
    return (
      <main className="auth-page" id="main-content">
        <section
          className="auth-card text-center"
          aria-labelledby="page-title"
        >
          <p className="eyebrow">Відновлення пароля</p>
          <h1 id="page-title" className="mx-auto">
            Перевірте email
          </h1>
          <p className="leading-relaxed text-muted-foreground" role="status">
            {message}
          </p>
          <Link to="/login">Повернутися до входу</Link>
        </section>
      </main>
    );
  }

  const rootError = form.formState.errors.root?.message;

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card" aria-labelledby="page-title">
        <p className="eyebrow">Відновлення пароля</p>
        <h1 id="page-title">Забули пароль?</h1>
        <p className="leading-relaxed text-muted-foreground">
          Вкажіть email, і ми надішлемо посилання для встановлення нового пароля.
        </p>
        <Form {...form}>
          <form
            noValidate
            ref={formRef}
            onSubmit={onSubmit}
            className="mt-8 grid gap-5"
          >
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Email</FormLabel>
                  <FormControl>
                    <Input
                      type="email"
                      autoComplete="email"
                      spellCheck={false}
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            {rootError && (
              <p className="m-0 text-[0.88rem] text-destructive" role="alert">
                {rootError}
              </p>
            )}
            <Button
              className="mt-2 justify-self-start"
              disabled={form.formState.isSubmitting}
              type="submit"
            >
              {form.formState.isSubmitting ? "Надсилаємо…" : "Надіслати інструкції"}
            </Button>
          </form>
        </Form>
        <p className="leading-relaxed text-muted-foreground">
          <Link to="/login">Повернутися до входу</Link>
        </p>
      </section>
    </main>
  );
}
