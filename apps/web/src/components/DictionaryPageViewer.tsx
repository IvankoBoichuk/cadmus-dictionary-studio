import { useEffect, useState } from "react";

import { dictionaryPageImageUrl, type LexemeResponse, type LexemeSuggestion } from "../api";
import { useDeleteLexeme } from "../hooks/useDeleteLexeme";
import { useDictionaryPagesSummary } from "../hooks/useDictionaryPagesSummary";
import { useLexemesForPage } from "../hooks/useLexemesForPage";
import { useOcrSuggestions } from "../hooks/useOcrSuggestions";
import { lexemeToUpdateInput, useUpdateLexeme } from "../hooks/useUpdateLexeme";
import { LexemeCanvas } from "./LexemeCanvas";
import { LexemeList } from "./LexemeList";
import { ScanProgressBar } from "./ScanProgressBar";

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
  const {
    state: lexemesState,
    addLexeme,
    updateLexeme,
    removeLexeme,
  } = useLexemesForPage(dictionaryId, currentPage);
  const { state: updateState, submit: submitUpdate } = useUpdateLexeme(dictionaryId);
  const { remove: deleteLexeme } = useDeleteLexeme(dictionaryId);
  const {
    state: ocrState,
    trigger: triggerOcrSuggestions,
    dismissSuggestion,
    reset: resetOcrSuggestions,
  } = useOcrSuggestions(dictionaryId, currentPage);

  const [selectedLexemeId, setSelectedLexemeId] = useState<string | null>(null);
  const [redrawingLexemeId, setRedrawingLexemeId] = useState<string | null>(null);
  const [secondBoxDraftLexemeId, setSecondBoxDraftLexemeId] = useState<string | null>(
    null,
  );
  const pageKey = `${dictionaryId}:${currentPage}`;
  const [previousPageKey, setPreviousPageKey] = useState(pageKey);
  if (pageKey !== previousPageKey) {
    setPreviousPageKey(pageKey);
    setSelectedLexemeId(null);
    setRedrawingLexemeId(null);
    setSecondBoxDraftLexemeId(null);
    resetOcrSuggestions();
  }

  const suggestions: LexemeSuggestion[] =
    ocrState.status === "succeeded" ? ocrState.suggestions : [];

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

  const handleStartRedraw = (lexemeId: string) => {
    setSelectedLexemeId(lexemeId);
    setRedrawingLexemeId(lexemeId);
    setSecondBoxDraftLexemeId(null);
  };

  const handleLexemeRedrawn = (lexeme: LexemeResponse) => {
    updateLexeme(lexeme);
    setRedrawingLexemeId(null);
  };

  const findLexeme = (lexemeId: string): LexemeResponse | undefined =>
    lexemesState.status === "loaded"
      ? lexemesState.lexemes.find((lexeme) => lexeme.id === lexemeId)
      : undefined;

  const handleSaveText = (lexemeId: string, newText: string) => {
    const target = findLexeme(lexemeId);
    if (!target) return;
    void submitUpdate(lexemeId, {
      ...lexemeToUpdateInput(target),
      source_text: newText,
    }).then((updated) => {
      if (updated) updateLexeme(updated);
    });
  };

  const handleStartAddSecondBox = (lexemeId: string) => {
    setSelectedLexemeId(lexemeId);
    setSecondBoxDraftLexemeId(lexemeId);
    setRedrawingLexemeId(null);
  };

  const handleSecondBoxDrawn = (lexeme: LexemeResponse) => {
    updateLexeme(lexeme);
    setSecondBoxDraftLexemeId(null);
  };

  const handleRemoveSecondBox = (lexemeId: string) => {
    const target = findLexeme(lexemeId);
    if (!target) return;
    void submitUpdate(lexemeId, {
      ...lexemeToUpdateInput(target),
      x2: null,
      y2: null,
      width2: null,
      height2: null,
    }).then((updated) => {
      if (updated) updateLexeme(updated);
    });
  };

  const handleMarkComplete = (lexemeId: string) => {
    const target = findLexeme(lexemeId);
    if (!target) return;
    if (!window.confirm("Позначити лексему завершеною? Її більше не можна редагувати.")) {
      return;
    }
    void submitUpdate(lexemeId, {
      ...lexemeToUpdateInput(target),
      status: "complete",
    }).then((updated) => {
      if (updated) updateLexeme(updated);
    });
  };

  const handleDelete = (lexemeId: string) => {
    void deleteLexeme(lexemeId).then((deleted) => {
      if (!deleted) return;
      removeLexeme(lexemeId);
      if (selectedLexemeId === lexemeId) setSelectedLexemeId(null);
      if (redrawingLexemeId === lexemeId) setRedrawingLexemeId(null);
      if (secondBoxDraftLexemeId === lexemeId) setSecondBoxDraftLexemeId(null);
    });
  };

  return (
    <div className="page-viewer" aria-labelledby="page-viewer-heading">
      <h2 id="page-viewer-heading" className="visually-hidden">
        Перегляд сторінки словника
      </h2>
      <div className="ocr-suggestions-controls">
        <button
          type="button"
          className="secondary-button"
          onClick={() => void triggerOcrSuggestions()}
          disabled={
            ocrState.status === "starting" ||
            ocrState.status === "queued" ||
            ocrState.status === "running"
          }
        >
          {ocrState.status === "starting" ||
          ocrState.status === "queued" ||
          ocrState.status === "running"
            ? "Розпізнаємо слова…"
            : "Автоматично знайти слова (OCR)"}
        </button>
        {ocrState.status === "succeeded" && (
          <span className="lede" role="status">
            Знайдено пропозицій: {ocrState.suggestions.length}
          </span>
        )}
        {ocrState.status === "failed" && (
          <span className="form-error" role="alert">
            {ocrState.message}
          </span>
        )}
      </div>
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
          redrawingLexemeId={redrawingLexemeId}
          onLexemeRedrawn={handleLexemeRedrawn}
          onCancelRedraw={() => setRedrawingLexemeId(null)}
          onSubmitUpdate={submitUpdate}
          suggestions={suggestions}
          onAcceptSuggestion={dismissSuggestion}
          secondBoxDraftLexemeId={secondBoxDraftLexemeId}
          onSecondBoxDrawn={handleSecondBoxDrawn}
          onCancelSecondBoxDraft={() => setSecondBoxDraftLexemeId(null)}
        />
        <aside className="lexeme-sidebar" aria-labelledby="lexeme-list-heading">
          <h3 id="lexeme-list-heading">Лексеми сторінки</h3>
          <LexemeList
            lexemesState={lexemesState}
            pageNumber={currentPage}
            selectedLexemeId={selectedLexemeId}
            onSelectLexeme={setSelectedLexemeId}
            redrawingLexemeId={redrawingLexemeId}
            onStartRedraw={handleStartRedraw}
            onCancelRedraw={() => setRedrawingLexemeId(null)}
            onSaveText={handleSaveText}
            updateState={updateState}
            onDelete={handleDelete}
            secondBoxDraftLexemeId={secondBoxDraftLexemeId}
            onStartAddSecondBox={handleStartAddSecondBox}
            onCancelSecondBoxDraft={() => setSecondBoxDraftLexemeId(null)}
            onRemoveSecondBox={handleRemoveSecondBox}
            onMarkComplete={handleMarkComplete}
          />
        </aside>
      </div>
      <ScanProgressBar
        dictionaryId={dictionaryId}
        currentPage={currentPage}
        refreshToken={
          lexemesState.status === "loaded" ? lexemesState.lexemes.length : 0
        }
        onNavigate={onNavigate}
      />
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
