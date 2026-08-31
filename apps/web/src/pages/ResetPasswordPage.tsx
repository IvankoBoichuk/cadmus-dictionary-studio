import { useRef } from "react";
import { Link, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";

import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useResetPasswordForm } from "../hooks/useResetPasswordForm";

function InvalidLinkResult({ message }: { message: string }) {
  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card text-center" aria-labelledby="page-title">
        <p className="eyebrow">Відновлення пароля</p>
        <h1 id="page-title" className="mx-auto">
          Не вдалося відновити пароль
        </h1>
        <p className="leading-relaxed text-destructive" role="status">
          {message}
        </p>
        <Link to="/forgot-password">Надіслати новий запит</Link>
      </section>
    </main>
  );
}

export function ResetPasswordPage() {
  const location = useLocation();
  const token = new URLSearchParams(location.hash.slice(1)).get("token");
  const { form, onSubmit, message, tokenError } = useResetPasswordForm(
    token ?? "",
  );
  const formRef = useRef<HTMLFormElement>(null);

  useFocusFirstError(
    formRef,
    form.formState.submitCount,
    form.formState.isSubmitting,
  );

  if (!token) {
    return (
      <InvalidLinkResult message="У посиланні немає токена для відновлення пароля." />
    );
  }

  if (message) {
    return (
      <main className="auth-page" id="main-content">
        <section
          className="auth-card text-center"
          aria-labelledby="page-title"
        >
          <p className="eyebrow">Відновлення пароля</p>
          <h1 id="page-title" className="mx-auto">
            Пароль змінено
          </h1>
          <p className="leading-relaxed text-muted-foreground" role="status">
            {message}
          </p>
          <Link to="/login">Увійти</Link>
        </section>
      </main>
    );
  }

  if (tokenError) {
    return <InvalidLinkResult message={tokenError} />;
  }

  const rootError = form.formState.errors.root?.message;

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card" aria-labelledby="page-title">
        <p className="eyebrow">Відновлення пароля</p>
        <h1 id="page-title">Встановіть новий пароль</h1>
        <p className="leading-relaxed text-muted-foreground">
          Введіть і підтвердіть новий пароль для акаунта.
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
              name="new_password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Новий пароль</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      autoComplete="new-password"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>Щонайменше 12 символів.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="new_password_confirmation"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Підтвердження пароля</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      autoComplete="new-password"
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
              {form.formState.isSubmitting ? "Змінюємо пароль…" : "Змінити пароль"}
            </Button>
          </form>
        </Form>
      </section>
    </main>
  );
}
