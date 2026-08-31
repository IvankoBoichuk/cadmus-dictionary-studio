import { BrowserRouter, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AuthProvider } from "./components/AuthProvider";
import { PublicLayout } from "./components/PublicLayout";
import { AbbreviationsPage } from "./pages/AbbreviationsPage";
import { ArticleSchemaPage } from "./pages/ArticleSchemaPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DictionariesList } from "./pages/DictionariesList";
import { DictionaryFormPage } from "./pages/DictionaryFormPage";
import { DictionaryViewerPage } from "./pages/DictionaryViewerPage";
import { EntryDetailPage } from "./pages/EntryDetailPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PageRangesPage } from "./pages/PageRangesPage";
import { ProjectMembersPage } from "./pages/ProjectMembersPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { SettlementsPage } from "./pages/SettlementsPage";
import { StatusPage } from "./pages/StatusPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

export function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/status" element={<StatusPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route element={<AppShell />}>
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
            <Route
              path="/dictionaries/:dictionaryId/article-schema"
              element={<ArticleSchemaPage />}
            />
            <Route path="/entries/:entryId" element={<EntryDetailPage />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
