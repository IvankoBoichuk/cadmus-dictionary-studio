import { Navigate, useParams } from "react-router-dom";

import { PageRangeEditor } from "../components/PageRangeEditor";

export function PageRangesPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return (
    <>
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
    </>
  );
}
