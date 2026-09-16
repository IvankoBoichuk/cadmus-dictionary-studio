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
              className="w-full justify-self-start"
              disabled={form.formState.isSubmitting}
              type="submit"
            >
              {form.formState.isSubmitting ? "Входимо…" : "Увійти"}
            </Button>
          </form>
        </Form>
        <p className="my-3 text-center text-[0.88rem] text-muted-foreground">
          або
        </p>
        <a
          className="flex justify-center gap-3 rounded-full border border-input px-[0.8rem] py-[0.65rem] font-[650] text-foreground no-underline hover:border-primary hover:bg-[#f4f7f4] focus-visible:border-primary focus-visible:bg-[#f4f7f4] focus-visible:[outline:3px_solid_var(--color-ring-subtle)]"
          href={`${API_BASE_URL}/auth/google/start`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" height="24" viewBox="0 0 24 24" width="24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" data-alpine-devtools-right-click=""/><path d="M1 1h22v22H1z" fill="none"/></svg>
          <span>Продовжити з Google</span>
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
