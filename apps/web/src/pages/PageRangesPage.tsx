import { Navigate, useParams } from "react-router-dom";

import { PageRangeEditor } from "../components/PageRangeEditor";

export function PageRangesPage() {
  const { dictionaryId } = useParams<{ dictionaryId: string }>();

  if (!dictionaryId) {
    return <Navigate replace to="/dictionaries" />;
  }

  return (
    <>
      <h2 className="mb-2 text-[1.15rem]">Діапазони сторінок</h2>
      <p className="max-w-[60ch] text-[0.9rem] text-muted-foreground">
        Вкажіть один або декілька діапазонів сторінок PDF, що містять словникові
        статті, щоб Cadmus пропускав обкладинку, зміст та інші службові частини.
      </p>
      <div className="dictionary-form">
        <PageRangeEditor
          dictionaryId={dictionaryId}
          portalActionsInto="dictionary-header-actions"
        />
      </div>
    </>
  );
}
