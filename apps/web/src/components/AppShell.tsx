import {
  ClipboardCheck,
  LayoutDashboard,
  Library,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  UserRound,
  X,
} from "lucide-react";
import { Fragment, useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { useAuth } from "../authContext";
import { useLogout } from "../hooks/useLogout";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Дашборд", icon: LayoutDashboard, end: true },
  { to: "/dictionaries", label: "Словники", icon: Library, end: false },
  { to: "/review", label: "Черга рецензування", icon: ClipboardCheck, end: true },
] as const;

const SIDEBAR_COLLAPSED_KEY = "cadmus:sidebar-collapsed";

function readStoredCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

/** Chrome for authenticated routes: persistent sidebar + guarded `<main>`.
 * Public routes use `PublicLayout` (top-bar header) instead. */
export function AppShell() {
  const { session } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(readStoredCollapsed);

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
    } catch {
      // ignore storage errors (e.g. private browsing)
    }
  }, [collapsed]);

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
    <div className="min-h-screen lg:flex lg:h-screen lg:overflow-hidden">
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
        collapsed={collapsed}
        onToggleCollapsed={() => setCollapsed((value) => !value)}
      />
      <main
        id="main-content"
        className="w-full min-w-0 px-[clamp(1rem,4vw,2.5rem)] lg:h-full lg:flex-1 flex flex-col lg:overflow-y-auto"
      >
        <Outlet />
      </main>
      {/* Portal target for `DictionaryPageViewer`'s canvas area: rendered
       * here (after `#main-content`, aligned under it) instead of inline so
       * it escapes the entries grid layout. */}
      <div
        id="page-area-portal"
        className="w-full min-w-0 empty:hidden lg:h-full lg:flex-1 lg:overflow-hidden"
      />
    </div>
  );
}

function Sidebar({
  email,
  name,
  navOpen,
  onToggleNav,
  onCloseNav,
  collapsed,
  onToggleCollapsed,
}: {
  email: string;
  name: string | null;
  navOpen: boolean;
  onToggleNav: () => void;
  onCloseNav: () => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
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
    <div
      className={cn(
        "border-b bg-white/[0.72] lg:sticky lg:top-0 lg:h-screen lg:w-[16rem] lg:shrink-0 lg:self-start lg:border-r lg:border-b-0",
        collapsed && "lg:w-[4.5rem]",
      )}
    >
      <div
        className={cn(
          "flex min-h-[4.5rem] items-center justify-between gap-3 px-[6vw] lg:px-6",
          collapsed &&
            "lg:min-h-0 lg:flex-col lg:justify-center lg:gap-2 lg:px-2 lg:py-4",
        )}
      >
        <Link
          className="flex items-center gap-2 font-serif text-[1.45rem] font-bold tracking-[0.02em] no-underline"
          to="/dashboard"
          translate="no"
          aria-label="Cadmus — робочий простір"
          onClick={onCloseNav}
        >
          <img
            src="/logo.jpg"
            alt=""
            className="size-9 shrink-0 rounded-full object-cover"
          />
          <span className={cn(collapsed && "lg:hidden")}>Cadmus</span>
        </Link>
        <button
          type="button"
          className="hidden shrink-0 rounded-full p-2 text-muted-foreground hover:bg-accent hover:text-foreground lg:grid lg:place-items-center"
          aria-label={collapsed ? "Розгорнути бічну панель" : "Згорнути бічну панель"}
          onClick={onToggleCollapsed}
        >
          {collapsed ? (
            <PanelLeftOpen aria-hidden="true" className="size-5" />
          ) : (
            <PanelLeftClose aria-hidden="true" className="size-5" />
          )}
        </button>
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
          {NAV_ITEMS.map((item) => {
            const link = (
              <NavLink
                to={item.to}
                end={item.end}
                onClick={onCloseNav}
                className={({ isActive }) =>
                  cn(
                    "flex min-h-[2.75rem] items-center gap-3 rounded-md px-3 text-[0.95rem] font-[650] no-underline transition-[background-color,color] duration-[120ms] ease-out",
                    collapsed && "lg:justify-center lg:px-0",
                    isActive
                      ? "bg-secondary text-secondary-foreground"
                      : "text-foreground hover:bg-accent",
                  )
                }
              >
                <item.icon aria-hidden="true" className="size-[1.15rem] shrink-0" />
                <span className={cn(collapsed && "lg:hidden")}>{item.label}</span>
              </NavLink>
            );

            if (!collapsed) {
              return <Fragment key={item.to}>{link}</Fragment>;
            }

            return (
              <Tooltip key={item.to}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right">{item.label}</TooltipContent>
              </Tooltip>
            );
          })}
        </nav>
        <div className="mt-6 border-t pt-4 lg:mt-auto">
          {(() => {
            const accountLink = (
              <NavLink
                to="/account"
                onClick={onCloseNav}
                title={email}
                className={({ isActive }) =>
                  cn(
                    "mb-2 flex min-h-[2.75rem] items-center gap-3 rounded-md px-3 no-underline transition-[background-color,color] duration-[120ms] ease-out",
                    collapsed && "lg:justify-center lg:px-0",
                    isActive
                      ? "bg-secondary text-secondary-foreground"
                      : "text-foreground hover:bg-accent",
                  )
                }
              >
                <UserRound aria-hidden="true" className="size-[1.15rem] shrink-0" />
                <span className={cn("min-w-0", collapsed && "lg:hidden")}>
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
            );

            if (!collapsed) return accountLink;

            return (
              <Tooltip>
                <TooltipTrigger asChild>{accountLink}</TooltipTrigger>
                <TooltipContent side="right">{name ?? email}</TooltipContent>
              </Tooltip>
            );
          })()}
          {(() => {
            const logoutButton = (
              <Button
                type="button"
                variant="secondary"
                className={cn("w-full", collapsed && "lg:px-0")}
                disabled={state.status === "submitting"}
                onClick={logout}
              >
                <span className={cn(collapsed && "lg:hidden")}>
                  {state.status === "submitting" ? "Виходимо…" : "Вийти"}
                </span>
                <LogOut
                  aria-hidden="true"
                  className={cn("hidden size-4", collapsed && "lg:inline")}
                />
              </Button>
            );

            if (!collapsed) return logoutButton;

            return (
              <Tooltip>
                <TooltipTrigger asChild>{logoutButton}</TooltipTrigger>
                <TooltipContent side="right">Вийти</TooltipContent>
              </Tooltip>
            );
          })()}
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
