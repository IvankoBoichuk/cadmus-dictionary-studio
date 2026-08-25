import { BrowserRouter, Link, Route, Routes } from "react-router-dom";

import { ApiStatus } from "./components/ApiStatus";
import { AuthActions } from "./components/AuthActions";
import { AuthProvider } from "./components/AuthProvider";
import { AbbreviationsPage } from "./pages/AbbreviationsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DictionariesList } from "./pages/DictionariesList";
import { DictionaryFormPage } from "./pages/DictionaryFormPage";
import { DictionaryViewerPage } from "./pages/DictionaryViewerPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { PageRangesPage } from "./pages/PageRangesPage";
import { ProjectMembersPage } from "./pages/ProjectMembersPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { SettlementsPage } from "./pages/SettlementsPage";
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
            <Route path="/dictionaries/new" element={<DictionaryFormPage />} />
            <Route path="/dictionaries" element={<DictionariesList />} />
            <Route
              path="/dictionaries/:dictionaryId/edit"
              element={<DictionaryFormPage />}
            />
            <Route
              path="/dictionaries/:dictionaryId/abbreviations"
              element={<AbbreviationsPage />}
            />
            <Route
              path="/dictionaries/:dictionaryId/settlements"
              element={<SettlementsPage />}
            />
            <Route
              path="/dictionaries/:dictionaryId/page-ranges"
              element={<PageRangesPage />}
            />
            <Route
              path="/dictionaries/:dictionaryId/members"
              element={<ProjectMembersPage />}
            />
            <Route
              path="/dictionaries/:dictionaryId/view"
              element={<DictionaryViewerPage />}
            />
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
