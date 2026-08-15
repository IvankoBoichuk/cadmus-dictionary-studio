import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { ApiStatus } from "./components/ApiStatus";
import { RegisterPage } from "./pages/RegisterPage";
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
        <Link className="primary-link" to="/register">
          Зареєструватися
        </Link>
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
      <div className="app-shell">
        <a className="skip-link" href="#main-content">
          Перейти до вмісту
        </a>
        <header className="site-header">
          <Link className="brand" to="/" aria-label="Cadmus — головна">
            Cadmus
          </Link>
        </header>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
