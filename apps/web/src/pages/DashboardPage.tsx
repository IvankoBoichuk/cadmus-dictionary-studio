import { Link, Navigate } from "react-router-dom";

import { Button } from "@/components/ui/button";

import { useAuth } from "../authContext";

export function DashboardPage() {
  const { session } = useAuth();
  if (session.status === "loading") {
    return (
      <main className="page" id="main-content">
        <p role="status">Завантажуємо робочий простір…</p>
      </main>
    );
  }
  if (session.status !== "authenticated") {
    return <Navigate replace to="/login" />;
  }
  return (
    <main className="page" id="main-content">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Панель</p>
        <h1 id="page-title">Робочий простір</h1>
        <p className="lede">Ви увійшли як {session.user.email}.</p>
        <Button asChild className="mt-4 px-[1.1rem] py-3">
          <Link to="/dictionaries/new">Додати словник</Link>
        </Button>
        <Link
          className="ml-4 inline-block font-[650] text-primary hover:underline"
          to="/dictionaries"
        >
          Мої словники
        </Link>
      </section>
    </main>
  );
}
