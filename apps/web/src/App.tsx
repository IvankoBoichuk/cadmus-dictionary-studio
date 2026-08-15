import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { ApiStatus } from "./components/ApiStatus";
import { AuthActions } from "./components/AuthActions";
import { AuthProvider } from "./components/AuthProvider";
import { DashboardPage } from "./pages/DashboardPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

function HomePage() {
  return (
    <main className="page" id="main-content">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Lexicographic workspace</p>
        <h1 id="page-title">Cadmus Dictionary Studio</h1>
        <p className="lede">
          Основа інтерфейсу для перетворення сканів словників на перевірені
          структуровані дані.
        </p>
      </section>
      <ApiStatus />
    </main>
  );
}

function NotFoundPage() {
  return (
    <main className="page" id="main-content">
      <h1>Сторінку не знайдено</h1>
      <p>
        <Link to="/">Повернутися на головну</Link>
      </p>
    </main>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="app-shell">
          <a className="skip-link" href="#main-content">
            Перейти до вмісту
          </a>
          <header className="site-header">
            <Link className="brand" to="/" aria-label="Cadmus — головна">
              Cadmus
            </Link>
            <AuthActions />
          </header>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
