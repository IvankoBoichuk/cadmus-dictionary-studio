import { LayoutDashboard, Library, Menu, UserRound, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { useAuth } from "../authContext";
import { useLogout } from "../hooks/useLogout";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Дашборд", icon: LayoutDashboard, end: true },
  { to: "/dictionaries", label: "Словники", icon: Library, end: false },
] as const;

/** Chrome for authenticated routes: persistent sidebar + guarded `<main>`.
 * Public routes use `PublicLayout` (top-bar header) instead. */
export function AppShell() {
  const { session } = useAuth();
  const [navOpen, setNavOpen] = useState(false);

  if (session.status === "loading") {
    return (
      <div className="grid min-h-screen place-items-center p-8">
        <p role="status">Завантажуємо робочий простір…</p>
      </div>
    );
  }
  if (session.status !== "authenticated") {
    return <Navigate replace to="/login" />;
  }

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[16rem_1fr]">
      <a
        className="fixed top-4 left-4 z-[2] -translate-y-[180%] bg-foreground px-4 py-3 text-white focus:translate-y-0"
        href="#main-content"
      >
        Перейти до вмісту
      </a>
      <Sidebar
        email={session.user.email}
        name={session.user.name ?? null}
        navOpen={navOpen}
        onToggleNav={() => setNavOpen((open) => !open)}
        onCloseNav={() => setNavOpen(false)}
      />
      <main
        id="main-content"
        className="w-full min-w-0 px-[clamp(1rem,4vw,2.5rem)] py-[clamp(2rem,6vw,3.5rem)]"
      >
        <Outlet />
      </main>
    </div>
  );
}

function Sidebar({
  email,
  name,
  navOpen,
  onToggleNav,
  onCloseNav,
}: {
  email: string;
  name: string | null;
  navOpen: boolean;
  onToggleNav: () => void;
  onCloseNav: () => void;
}) {
  const { state, logout } = useLogout();

  useEffect(() => {
    if (!navOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseNav();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [navOpen, onCloseNav]);

  return (
    <div className="border-b bg-white/[0.72] lg:sticky lg:top-0 lg:h-screen lg:self-start lg:border-r lg:border-b-0">
      <div className="flex min-h-[4.5rem] items-center justify-between gap-3 px-[6vw] lg:px-6">
        <Link
          className="font-serif text-[1.45rem] font-bold tracking-[0.02em] no-underline"
          to="/dashboard"
          translate="no"
          aria-label="Cadmus — робочий простір"
          onClick={onCloseNav}
        >
          Cadmus
        </Link>
        <button
          type="button"
          className="grid size-11 shrink-0 place-items-center rounded-full bg-secondary text-secondary-foreground lg:hidden"
          aria-expanded={navOpen}
          aria-controls="app-nav"
          aria-label={navOpen ? "Закрити меню" : "Відкрити меню"}
          onClick={onToggleNav}
        >
          {navOpen ? (
            <X aria-hidden="true" className="size-5" />
          ) : (
            <Menu aria-hidden="true" className="size-5" />
          )}
        </button>
      </div>
      <div
        id="app-nav"
        className={cn(
          "flex-col gap-6 px-[6vw] pb-4 lg:h-[calc(100vh-4.5rem)] lg:px-4 lg:pb-6",
          navOpen ? "flex" : "hidden lg:flex",
        )}
      >
        <nav aria-label="Основна навігація" className="flex flex-col gap-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={onCloseNav}
              className={({ isActive }) =>
                cn(
                  "flex min-h-[2.75rem] items-center gap-3 rounded-md px-3 text-[0.95rem] font-[650] no-underline transition-[background-color,color] duration-[120ms] ease-out",
                  isActive
                    ? "bg-secondary text-secondary-foreground"
                    : "text-foreground hover:bg-accent",
                )
              }
            >
              <item.icon aria-hidden="true" className="size-[1.15rem] shrink-0" />
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-6 border-t pt-4 lg:mt-auto">
          <NavLink
            to="/account"
            onClick={onCloseNav}
            title={email}
            className={({ isActive }) =>
              cn(
                "mb-2 flex min-h-[2.75rem] items-center gap-3 rounded-md px-3 no-underline transition-[background-color,color] duration-[120ms] ease-out",
                isActive
                  ? "bg-secondary text-secondary-foreground"
                  : "text-foreground hover:bg-accent",
              )
            }
          >
            <UserRound aria-hidden="true" className="size-[1.15rem] shrink-0" />
            <span className="min-w-0">
              <span className="block truncate text-[0.9rem] font-[650]">
                {name ?? email}
              </span>
              {name && (
                <span className="block truncate text-[0.8rem] font-normal text-muted-foreground">
                  {email}
                </span>
              )}
            </span>
          </NavLink>
          <Button
            type="button"
            variant="secondary"
            className="w-full"
            disabled={state.status === "submitting"}
            onClick={logout}
          >
            {state.status === "submitting" ? "Виходимо…" : "Вийти"}
          </Button>
          {state.status === "error" && (
            <p className="mt-2 text-[0.85rem] text-destructive" role="alert">
              {state.message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
