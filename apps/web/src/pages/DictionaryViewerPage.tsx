import { Navigate, useParams, useSearchParams } from "react-router-dom";

import { DictionaryPageViewer } from "../components/DictionaryPageViewer";

/** BH-53: the ``page`` query param keeps the current page across reloads. */
export function DictionaryViewerPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();

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
    <>
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
    </>
  );
}
