import { Navigate, useParams, useSearchParams } from "react-router-dom";

import { useAuth } from "../authContext";
import { DictionaryPageViewer } from "../components/DictionaryPageViewer";

/** BH-53: the ``page`` query param keeps the current page across reloads. */
export function DictionaryViewerPage() {
  const { session } = useAuth();
  const { dictionaryId } = useParams<{ dictionaryId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

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
  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  const requestedPage = Number.parseInt(searchParams.get("page") ?? "1", 10);
  const pageNumber =
    Number.isFinite(requestedPage) && requestedPage > 0 ? requestedPage : 1;

  const handleNavigate = (nextPage: number) => {
    setSearchParams(
      (previous) => {
        const next = new URLSearchParams(previous);
        next.set("page", String(nextPage));
        return next;
      },
      { replace: true },
    );
  };

  return (
    <main className="page" id="main-content">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Словник</p>
        <h1 id="page-title">Перегляд сторінок</h1>
        <p className="lede">Перегляньте сторінки словника послідовно.</p>
      </section>
      <DictionaryPageViewer
        dictionaryId={dictionaryId}
        pageNumber={pageNumber}
        onNavigate={handleNavigate}
      />
    </main>
  );
}
