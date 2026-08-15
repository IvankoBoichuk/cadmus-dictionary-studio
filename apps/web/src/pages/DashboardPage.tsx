import { Navigate } from "react-router-dom";

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
        <p className="eyebrow">Dashboard</p>
        <h1 id="page-title">Робочий простір</h1>
        <p className="lede">Ви увійшли як {session.user.email}.</p>
      </section>
    </main>
  );
}
