import { useEffect, useState } from "react";

import { dictionaryPageImageUrl } from "../api";
import { useDictionaryPagesSummary } from "../hooks/useDictionaryPagesSummary";
import { useLexemesForPage } from "../hooks/useLexemesForPage";
import { LexemeCanvas } from "./LexemeCanvas";
import { LexemeList } from "./LexemeList";

/** BH-53: paginated viewer over a dictionary's rendered, in-range pages. */
export function DictionaryPageViewer({
  dictionaryId,
  pageNumber,
  onNavigate,
}: {
  dictionaryId: string;
  pageNumber: number;
  onNavigate: (pageNumber: number) => void;
}) {
  const summary = useDictionaryPagesSummary(dictionaryId);
  const totalPages = summary.status === "loaded" ? summary.totalPages : null;

  useEffect(() => {
    if (totalPages === null || totalPages === 0) return;
    const clamped = Math.min(Math.max(pageNumber, 1), totalPages);
    if (clamped !== pageNumber) onNavigate(clamped);
  }, [totalPages, pageNumber, onNavigate]);

  const currentPage = Math.min(Math.max(pageNumber, 1), totalPages ?? pageNumber);
  const { state: lexemesState, addLexeme } = useLexemesForPage(
    dictionaryId,
    currentPage,
  );
  const [selectedLexemeId, setSelectedLexemeId] = useState<string | null>(null);
  const pageKey = `${dictionaryId}:${currentPage}`;
  const [previousPageKey, setPreviousPageKey] = useState(pageKey);
  if (pageKey !== previousPageKey) {
    setPreviousPageKey(pageKey);
    setSelectedLexemeId(null);
  }

  if (summary.status === "loading") {
    return <p role="status">Завантажуємо сторінки…</p>;
  }
  if (summary.status === "error") {
    return (
      <p className="form-error" role="alert">
        {summary.message}
      </p>
    );
  }
  if (summary.totalPages === 0) {
    return (
      <p className="lede">
        Для цього словника ще не вказано жодного діапазону сторінок для обробки.
      </p>
    );
  }

  return (
    <div className="page-viewer" aria-labelledby="page-viewer-heading">
      <h2 id="page-viewer-heading" className="visually-hidden">
        Перегляд сторінки словника
      </h2>
      <div className="page-viewer-body">
        <LexemeCanvas
          dictionaryId={dictionaryId}
          pageNumber={currentPage}
          imageUrl={dictionaryPageImageUrl(dictionaryId, currentPage)}
          imageAlt={`Сторінка ${currentPage} з ${summary.totalPages}`}
          lexemes={lexemesState.status === "loaded" ? lexemesState.lexemes : []}
          onLexemeCreated={addLexeme}
          selectedLexemeId={selectedLexemeId}
          onSelectLexeme={setSelectedLexemeId}
        />
        <aside className="lexeme-sidebar" aria-labelledby="lexeme-list-heading">
          <h3 id="lexeme-list-heading">Лексеми сторінки</h3>
          <LexemeList
            lexemesState={lexemesState}
            pageNumber={currentPage}
            selectedLexemeId={selectedLexemeId}
            onSelectLexeme={setSelectedLexemeId}
          />
        </aside>
      </div>
      <div className="page-viewer-nav">
        <button
          type="button"
          className="secondary-button"
          onClick={() => onNavigate(currentPage - 1)}
          disabled={currentPage <= 1}
        >
          ← Попередня
        </button>
        <span className="page-viewer-counter" role="status">
          Сторінка {currentPage} / {summary.totalPages}
        </span>
        <button
          type="button"
          className="secondary-button"
          onClick={() => onNavigate(currentPage + 1)}
          disabled={currentPage >= summary.totalPages}
        >
          Наступна →
        </button>
      </div>
    </div>
  );
}
