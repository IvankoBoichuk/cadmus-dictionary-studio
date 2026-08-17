import { Navigate, useParams } from "react-router-dom";

import { useAuth } from "../authContext";
import { PageRangeEditor } from "../components/PageRangeEditor";

export function PageRangesPage() {
  const { session } = useAuth();
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

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

  return (
    <main className="page" id="main-content">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Словник</p>
        <h1 id="page-title">Діапазони сторінок</h1>
        <p className="lede">
          Вкажіть один або декілька діапазонів сторінок PDF, що містять словникові
          статті, щоб Cadmus пропускав обкладинку, зміст та інші службові частини.
        </p>
      </section>
      <div className="dictionary-form">
        <PageRangeEditor dictionaryId={dictionaryId} />
      </div>
    </main>
  );
}
