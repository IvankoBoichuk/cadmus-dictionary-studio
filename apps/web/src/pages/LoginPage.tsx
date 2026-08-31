import { useRef } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";

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

import { API_BASE_URL } from "../config";
import { useFocusFirstError } from "../hooks/useFocusFirstError";
import { useLoginForm } from "../hooks/useLoginForm";
import { useAuth } from "../authContext";

function LoginForm({ sessionUnavailable }: { sessionUnavailable: boolean }) {
  const { form, onSubmit } = useLoginForm();
  const formRef = useRef<HTMLFormElement>(null);
  const [searchParams] = useSearchParams();

  useFocusFirstError(
    formRef,
    form.formState.submitCount,
    form.formState.isSubmitting,
  );
  const googleAuthFailed = searchParams.get("error") === "google_auth_failed";
  const rootError = form.formState.errors.root?.message;

  return (
    <main className="auth-page" id="main-content">
      <section className="auth-card" aria-labelledby="page-title">
        <p className="eyebrow">Робочий простір</p>
        <h1 id="page-title">Увійти</h1>
        <p className="leading-relaxed text-muted-foreground">
          Увійдіть за допомогою email і пароля, щоб продовжити роботу.
        </p>
        {sessionUnavailable && (
          <p className="m-0 text-[0.88rem] text-destructive" role="alert">
            Не вдалося перевірити поточну сесію. Ви можете спробувати увійти.
          </p>
        )}
        {googleAuthFailed && (
          <p className="m-0 text-[0.88rem] text-destructive" role="alert">
            Не вдалося увійти через Google. Спробуйте ще раз або скористайтеся
            email і паролем.
          </p>
        )}
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
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>Пароль</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      autoComplete="current-password"
                      {...field}
                    />
                  </FormControl>
                  <FormMessage />
                  <p className="m-0 text-[0.88rem] text-muted-foreground">
                    <Link to="/forgot-password">Забули пароль?</Link>
                  </p>
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
              {form.formState.isSubmitting ? "Входимо…" : "Увійти"}
            </Button>
          </form>
        </Form>
        <p className="my-6 text-center text-[0.88rem] text-muted-foreground">
          або
        </p>
        <a
          className="flex justify-center rounded-[0.55rem] border border-input px-[0.8rem] py-[0.65rem] font-[650] text-foreground no-underline hover:border-primary hover:bg-[#f4f7f4] focus-visible:border-primary focus-visible:bg-[#f4f7f4] focus-visible:[outline:3px_solid_var(--color-ring-subtle)]"
          href={`${API_BASE_URL}/auth/google/start`}
        >
          Продовжити з Google
        </a>
      </section>
    </main>
  );
}

export function LoginPage() {
  const { session } = useAuth();
  if (session.status === "loading") {
    return (
      <main className="auth-page" id="main-content">
        <p role="status">Перевіряємо сесію…</p>
      </main>
    );
  }
  if (session.status === "authenticated") {
    return <Navigate replace to="/dashboard" />;
  }
  return <LoginForm sessionUnavailable={session.status === "unavailable"} />;
}
