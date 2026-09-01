import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/AppShell";
import { AuthProvider } from "./components/AuthProvider";
import { DictionaryLayout } from "./components/DictionaryLayout";
import { DictionarySettingsLayout } from "./components/DictionarySettingsLayout";
import { PublicLayout } from "./components/PublicLayout";
import { AbbreviationsPage } from "./pages/AbbreviationsPage";
import { AccountPage } from "./pages/AccountPage";
import { ArticleSchemaPage } from "./pages/ArticleSchemaPage";
import { ConfirmEmailChangePage } from "./pages/ConfirmEmailChangePage";
import { DashboardPage } from "./pages/DashboardPage";
import { DictionariesList } from "./pages/DictionariesList";
import { DictionaryMetadataPage } from "./pages/DictionaryMetadataPage";
import { DictionaryOverviewPage } from "./pages/DictionaryOverviewPage";
import { DictionaryTasksPage } from "./pages/DictionaryTasksPage";
import { DictionaryWorkspacePage } from "./pages/DictionaryWorkspacePage";
import { EntriesListPage } from "./pages/EntriesListPage";
import { EntryDetailPage } from "./pages/EntryDetailPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { NewDictionaryPage } from "./pages/NewDictionaryPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PageRangesPage } from "./pages/PageRangesPage";
import { ProjectMembersPage } from "./pages/ProjectMembersPage";
import { ReferenceLexiconPage } from "./pages/ReferenceLexiconPage";
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
            <Route
              path="/confirm-email-change"
              element={<ConfirmEmailChangePage />}
            />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/account" element={<AccountPage />} />
            <Route path="/dictionaries" element={<DictionariesList />} />
            <Route path="/dictionaries/new" element={<NewDictionaryPage />} />
            <Route
              path="/dictionaries/:dictionaryId"
              element={<DictionaryLayout />}
            >
              <Route index element={<DictionaryOverviewPage />} />
              <Route path="pages" element={<DictionaryWorkspacePage />} />
              <Route path="entries" element={<EntriesListPage />} />
              <Route path="tasks" element={<DictionaryTasksPage />} />
              <Route path="settings" element={<DictionarySettingsLayout />}>
                <Route index element={<Navigate replace to="metadata" />} />
                <Route path="metadata" element={<DictionaryMetadataPage />} />
                <Route path="page-ranges" element={<PageRangesPage />} />
                <Route path="abbreviations" element={<AbbreviationsPage />} />
                <Route path="settlements" element={<SettlementsPage />} />
                <Route path="article-schema" element={<ArticleSchemaPage />} />
                <Route path="members" element={<ProjectMembersPage />} />
              </Route>
            </Route>
            <Route path="/entries/:entryId" element={<EntryDetailPage />} />
            <Route
              path="/reference-lexicons/:code"
              element={<ReferenceLexiconPage />}
            />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
