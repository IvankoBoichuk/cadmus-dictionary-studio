import { Link, Outlet } from "react-router-dom";

import { AuthActions } from "./AuthActions";

/** Chrome for public, unauthenticated routes: brand header + footer nav.
 * Authenticated routes use `AppShell` (sidebar) instead. */
export function PublicLayout() {
  return (
    <div className="flex min-h-screen flex-col">
      <a
        className="fixed top-4 left-4 z-[2] -translate-y-[180%] bg-foreground px-4 py-3 text-white focus:translate-y-0"
        href="#main-content"
      >
        Перейти до вмісту
      </a>
      <header className="flex min-h-[4.5rem] items-center border-b bg-white/[0.72] px-[6vw]">
        <Link
          className="font-serif text-[1.45rem] font-bold tracking-[0.02em] no-underline"
          to="/"
          translate="no"
          aria-label="Cadmus — головна"
        >
          Cadmus
        </Link>
        <AuthActions />
      </header>
      <Outlet />
      <footer className="mt-auto border-t bg-white/[0.72] px-[6vw] py-6 text-[0.9rem] text-muted-foreground">
        <nav className="flex flex-wrap gap-x-6 gap-y-2" aria-label="Підвал">
          <Link className="hover:underline" to="/">
            Головна
          </Link>
          <Link className="hover:underline" to="/status">
            Стан системи
          </Link>
        </nav>
      </footer>
    </div>
  );
}
