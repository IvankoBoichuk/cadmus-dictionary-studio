import { MonitorSmartphone } from "lucide-react";
import type { ReactNode } from "react";

import type { SessionSummary } from "../api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
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

import { useAuth } from "../authContext";
import { formatDateTime } from "../format";
import { useChangeEmailForm } from "../hooks/useChangeEmailForm";
import { useChangePasswordForm } from "../hooks/useChangePasswordForm";
import { useProfileForm } from "../hooks/useProfileForm";
import { useSessions } from "../hooks/useSessions";

export function AccountPage() {
  const { session } = useAuth();
  const email = session.status === "authenticated" ? session.user.email : "";

  return (
    <>
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Акаунт</p>
        <h1 id="page-title">Мій профіль</h1>
        <p className="lede">
          Керуйте своїм іменем, електронною поштою, паролем і активними сесіями.
        </p>
      </section>

      <div className="mt-[clamp(2rem,6vw,3.5rem)] grid max-w-[46rem] gap-6">
        <ProfileSection />
        <EmailSection currentEmail={email} />
        <PasswordSection />
        <SessionsSection />
      </div>
    </>
  );
}

function SectionCard({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <Card className="p-[clamp(1.25rem,4vw,1.75rem)]">
      <h2 className="mb-1 text-[1.15rem]">{title}</h2>
      <p className="mb-5 text-[0.9rem] text-muted-foreground [text-wrap:pretty]">
        {description}
      </p>
      {children}
    </Card>
  );
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <p
      className="mt-4 text-[0.88rem] text-success-foreground"
      role="status"
    >
      {children}
    </p>
  );
}

function RootError({ message }: { message: string | undefined }) {
  if (!message) return null;
  return (
    <p className="mt-3 text-[0.88rem] text-destructive" role="alert">
      {message}
    </p>
  );
}

function ProfileSection() {
  const { form, onSubmit, saved } = useProfileForm();

  return (
    <SectionCard
      title="Ім’я"
      description="Показується у бічній панелі. Можна лишити порожнім."
    >
      <Form {...form}>
        <form noValidate onSubmit={onSubmit} className="grid gap-4">
          <FormField
            control={form.control}
            name="name"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Ім’я</FormLabel>
                <FormControl>
                  <Input autoComplete="name" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <RootError message={form.formState.errors.root?.message} />
          <Button
            className="justify-self-start"
            disabled={form.formState.isSubmitting}
            type="submit"
          >
            {form.formState.isSubmitting ? "Зберігаємо…" : "Зберегти"}
          </Button>
          {saved && <Notice>Ім’я збережено.</Notice>}
        </form>
      </Form>
    </SectionCard>
  );
}

function EmailSection({ currentEmail }: { currentEmail: string }) {
  const { form, onSubmit, message } = useChangeEmailForm();

  return (
    <SectionCard
      title="Електронна пошта"
      description="Поточна адреса використовується для входу. Нову адресу треба підтвердити за посиланням у листі."
    >
      <p className="mb-4 text-[0.9rem]">
        Поточна адреса:{" "}
        <span className="font-[650]" translate="no">
          {currentEmail}
        </span>
      </p>
      <Form {...form}>
        <form noValidate onSubmit={onSubmit} className="grid gap-4">
          <FormField
            control={form.control}
            name="new_email"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Нова адреса</FormLabel>
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
            name="current_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Поточний пароль</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    autoComplete="current-password"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <RootError message={form.formState.errors.root?.message} />
          <Button
            className="justify-self-start"
            disabled={form.formState.isSubmitting}
            type="submit"
          >
            {form.formState.isSubmitting ? "Надсилаємо…" : "Надіслати підтвердження"}
          </Button>
          {message && <Notice>{message}</Notice>}
        </form>
      </Form>
    </SectionCard>
  );
}

function PasswordSection() {
  const { form, onSubmit, message } = useChangePasswordForm();

  return (
    <SectionCard
      title="Пароль"
      description="Після зміни пароля всі інші пристрої буде виведено із системи."
    >
      <Form {...form}>
        <form noValidate onSubmit={onSubmit} className="grid gap-4">
          <FormField
            control={form.control}
            name="current_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Поточний пароль</FormLabel>
                <FormControl>
                  <Input
                    type="password"
                    autoComplete="current-password"
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <FormField
            control={form.control}
            name="new_password"
            render={({ field }) => (
              <FormItem>
                <FormLabel>Новий пароль</FormLabel>
                <FormControl>
                  <Input type="password" autoComplete="new-password" {...field} />
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
                  <Input type="password" autoComplete="new-password" {...field} />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
          <RootError message={form.formState.errors.root?.message} />
          <Button
            className="justify-self-start"
            disabled={form.formState.isSubmitting}
            type="submit"
          >
            {form.formState.isSubmitting ? "Змінюємо пароль…" : "Змінити пароль"}
          </Button>
          {message && <Notice>{message}</Notice>}
        </form>
      </Form>
    </SectionCard>
  );
}

function SessionsSection() {
  const { state, action, revoke, revokeOthers } = useSessions();

  const otherCount =
    state.status === "loaded"
      ? state.sessions.filter((s) => !s.current).length
      : 0;

  return (
    <SectionCard
      title="Активні сесії"
      description="Пристрої та браузери, у яких ви зараз увійшли."
    >
      {state.status === "loading" && (
        <p role="status" className="text-[0.9rem] text-muted-foreground">
          Завантажуємо сесії…
        </p>
      )}
      {state.status === "error" && (
        <p className="text-[0.88rem] text-destructive" role="alert">
          {state.message}
        </p>
      )}
      {state.status === "loaded" && (
        <>
          <ul className="m-0 grid list-none gap-2 p-0">
            {state.sessions.map((item) => (
              <SessionRow
                key={item.id}
                session={item}
                pending={action.pending}
                onRevoke={() => void revoke(item.id)}
              />
            ))}
          </ul>
          {action.error && (
            <p className="mt-3 text-[0.88rem] text-destructive" role="alert">
              {action.error}
            </p>
          )}
          {otherCount > 0 && (
            <Button
              type="button"
              variant="secondary"
              className="mt-4"
              disabled={action.pending}
              onClick={() => void revokeOthers()}
            >
              Вийти на інших пристроях ({otherCount})
            </Button>
          )}
        </>
      )}
    </SectionCard>
  );
}

function SessionRow({
  session,
  pending,
  onRevoke,
}: {
  session: SessionSummary;
  pending: boolean;
  onRevoke: () => void;
}) {
  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border p-3">
      <MonitorSmartphone
        aria-hidden="true"
        className="size-[1.15rem] shrink-0 text-muted-foreground"
      />
      <span className="min-w-0 grow text-[0.9rem]">
        <span className="block truncate font-[600]">
          {session.user_agent ?? "Невідомий пристрій"}
        </span>
        <span className="text-[0.82rem] text-muted-foreground">
          Вхід: {formatDateTime(session.created_at)} · діє до{" "}
          {formatDateTime(session.expires_at)}
        </span>
      </span>
      {session.current ? (
        <Badge variant="secondary">Цей пристрій</Badge>
      ) : (
        <Button
          type="button"
          variant="ghost"
          className="h-9 px-3 text-[0.85rem]"
          disabled={pending}
          onClick={onRevoke}
        >
          Вийти
        </Button>
      )}
    </li>
  );
}
