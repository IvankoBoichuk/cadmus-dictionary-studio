import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";

import {
  API,
  apiMessageFrom,
  dictionaryPageImageUrl,
  duplicateEntryFrom,
  type LexemeResponse,
  type LexemeSuggestion,
} from "../api";
import { clampZoom, ZOOM_STEP, type CanvasMode } from "../canvasTools";
import { formatNumber } from "../format";
import { useDeleteLexeme } from "../hooks/useDeleteLexeme";
import { useDictionaryPagesSummary } from "../hooks/useDictionaryPagesSummary";
import { useDictionaryScan } from "../hooks/useDictionaryScan";
import { useLexemesForPage } from "../hooks/useLexemesForPage";
import { useOcrSuggestions } from "../hooks/useOcrSuggestions";
import { useScanProgress } from "../hooks/useScanProgress";
import { lexemeToUpdateInput, useUpdateLexeme } from "../hooks/useUpdateLexeme";
import { CanvasToolbar } from "./CanvasToolbar";
import { LexemeCanvas } from "./LexemeCanvas";
import { LexemeList } from "./LexemeList";
import { PageNavigator } from "./PageNavigator";
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
  const navigate = useNavigate();
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
  const { state: scanState, trigger: triggerScan } = useDictionaryScan(dictionaryId);

  const [promotingLexemeId, setPromotingLexemeId] = useState<string | null>(null);
  const [promoteError, setPromoteError] = useState<string | null>(null);
  const [selectedLexemeId, setSelectedLexemeId] = useState<string | null>(null);
  const [redrawingLexemeId, setRedrawingLexemeId] = useState<string | null>(null);
  const [secondBoxDraftLexemeId, setSecondBoxDraftLexemeId] = useState<string | null>(
    null,
  );
  const [mode, setMode] = useState<CanvasMode>("select");
  const [zoom, setZoom] = useState(1);
  const pageKey = `${dictionaryId}:${currentPage}`;
  const [previousPageKey, setPreviousPageKey] = useState(pageKey);
  if (pageKey !== previousPageKey) {
    setPreviousPageKey(pageKey);
    setSelectedLexemeId(null);
    setRedrawingLexemeId(null);
    setSecondBoxDraftLexemeId(null);
    resetOcrSuggestions();
  }

  const lexemeCount =
    lexemesState.status === "loaded" ? lexemesState.lexemes.length : 0;

  // Derived (not effect-driven) from the queue's own progress counters, so the
  // page grid + bar below refetch live as the queue works, without a render pass.
  const scanToken =
    scanState.status === "queued" || scanState.status === "running"
      ? scanState.processedPages * 1000 + scanState.createdLexemes
      : scanState.status === "succeeded"
        ? 1_000_000 + scanState.processedPages * 1000 + scanState.createdLexemes
        : 0;
  const scanProgress = useScanProgress(dictionaryId, lexemeCount + scanToken);
  const progressPages =
    scanProgress.status === "loaded" ? scanProgress.progress.pages : [];
  const processedPages =
    scanProgress.status === "loaded" ? scanProgress.progress.processed_pages : 0;
  const progressTotalPages =
    scanProgress.status === "loaded"
      ? scanProgress.progress.total_pages
      : (totalPages ?? 0);

  const suggestions: LexemeSuggestion[] =
    ocrState.status === "succeeded" ? ocrState.suggestions : [];

  const ocrRunning =
    ocrState.status === "starting" ||
    ocrState.status === "queued" ||
    ocrState.status === "running";
  const scanRunning =
    scanState.status === "starting" ||
    scanState.status === "queued" ||
    scanState.status === "running";

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

  const handlePromoteToEntry = (lexemeId: string) => {
    setPromotingLexemeId(lexemeId);
    setPromoteError(null);
    API.lexemes.promote(dictionaryId, lexemeId).then(
      (entry) => navigate(`/entries/${entry.id}`),
      (error: unknown) => {
        const duplicate = duplicateEntryFrom(error);
        if (duplicate) {
          navigate(`/entries/${duplicate.entry_id}`);
          return;
        }
        setPromotingLexemeId(null);
        setPromoteError(
          apiMessageFrom(error) ?? "Не вдалося створити статтю з лексеми.",
        );
      },
    );
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
    <div className="grid gap-4" aria-labelledby="page-viewer-heading">
      <h2 id="page-viewer-heading" className="sr-only">
        Перегляд сторінки словника
      </h2>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          variant="secondary"
          type="button"
          onClick={() => void triggerOcrSuggestions()}
          disabled={ocrRunning}
        >
          {ocrRunning ? "Розпізнаємо слова…" : "Автоматично знайти слова (OCR)"}
        </Button>
        <Button
          variant="secondary"
          type="button"
          onClick={() => void triggerScan()}
          disabled={scanRunning}
        >
          {scanRunning
            ? "Опрацьовуємо чергу…"
            : "Запустити чергу OCR для всього словника"}
        </Button>
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
        {(scanState.status === "queued" || scanState.status === "running") && (
          <span className="lede" role="status">
            Опрацьовано {formatNumber(scanState.processedPages)} /{" "}
            {formatNumber(scanState.totalPages)} сторінок, створено лексем:{" "}
            {formatNumber(scanState.createdLexemes)}
          </span>
        )}
        {scanState.status === "succeeded" && (
          <span className="lede" role="status">
            Чергу завершено: опрацьовано {formatNumber(scanState.processedPages)}{" "}
            сторінок, створено лексем: {formatNumber(scanState.createdLexemes)}
          </span>
        )}
        {scanState.status === "failed" && (
          <span className="form-error" role="alert">
            {scanState.message}
          </span>
        )}
      </div>

      {promoteError && (
        <p className="form-error" role="alert">
          {promoteError}
        </p>
      )}

      <div className="grid w-full items-start gap-6 lg:grid-cols-[minmax(0,1.6fr)_minmax(24rem,1fr)]">
        <div className="grid gap-3 rounded-xl border border-border bg-surface p-3">
          <CanvasToolbar
            mode={mode}
            onModeChange={setMode}
            zoom={zoom}
            onZoomIn={() => setZoom((value) => clampZoom(value + ZOOM_STEP))}
            onZoomOut={() => setZoom((value) => clampZoom(value - ZOOM_STEP))}
            onZoomReset={() => setZoom(1)}
          />
          <PageNavigator
            pages={progressPages}
            currentPage={currentPage}
            totalPages={summary.totalPages}
            onNavigate={onNavigate}
          />
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
            mode={mode}
            zoom={zoom}
            onEraseLexeme={handleDelete}
          />
        </div>

        <section
          className="grid content-start gap-[0.6rem]"
          aria-labelledby="lexeme-list-heading"
        >
          <h3 id="lexeme-list-heading" className="text-base">
            Лексеми сторінки
          </h3>
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
            onPromoteToEntry={handlePromoteToEntry}
            promotingLexemeId={promotingLexemeId}
          />
        </section>
      </div>

      <ScanProgressBar processed={processedPages} total={progressTotalPages} />
    </div>
  );
}
