import { formatNumber } from "../format";
import { useDictionaryScan } from "../hooks/useDictionaryScan";
import { useScanProgress } from "../hooks/useScanProgress";

/** BH-57: shows scan progress and lets the user jump to an unprocessed page. */
export function ScanProgressBar({
  dictionaryId,
  currentPage,
  refreshToken,
  onNavigate,
}: {
  dictionaryId: string;
  currentPage: number;
  refreshToken: number;
  onNavigate: (pageNumber: number) => void;
}) {
  const { state: scanState, trigger: triggerScan } = useDictionaryScan(dictionaryId);

  // Derived (not effect-driven) from the queue's own progress counters, so
  // the progress grid below refetches live as the queue works through the
  // dictionary's pages, without a separate render pass.
  const scanToken =
    scanState.status === "queued" || scanState.status === "running"
      ? scanState.processedPages * 1000 + scanState.createdLexemes
      : scanState.status === "succeeded"
        ? 1_000_000 + scanState.processedPages * 1000 + scanState.createdLexemes
        : 0;

  const state = useScanProgress(dictionaryId, refreshToken + scanToken);

  const scanRunning =
    scanState.status === "starting" ||
    scanState.status === "queued" ||
    scanState.status === "running";

  const scanControls = (
    <div className="ocr-suggestions-controls">
      <button
        type="button"
        className="secondary-button"
        onClick={() => void triggerScan()}
        disabled={scanRunning}
      >
        {scanRunning
          ? "Опрацьовуємо чергу…"
          : "Запустити чергу OCR для всього словника"}
      </button>
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
  );

  if (state.status === "loading") {
    return (
      <>
        {scanControls}
        <p role="status">Завантажуємо прогрес сканування…</p>
      </>
    );
  }
  if (state.status === "error") {
    return (
      <>
        {scanControls}
        <p className="form-error" role="alert">
          {state.message}
        </p>
      </>
    );
  }

  const { progress } = state;
  const percent =
    progress.total_pages === 0
      ? 0
      : Math.round((progress.processed_pages / progress.total_pages) * 100);

  const findNextUnprocessed = (): number | null => {
    const after = progress.pages.find(
      (page) => page.page_number > currentPage && !page.has_lexemes,
    );
    if (after) return after.page_number;
    const fromStart = progress.pages.find((page) => !page.has_lexemes);
    return fromStart ? fromStart.page_number : null;
  };

  const handleJumpToUnprocessed = () => {
    const next = findNextUnprocessed();
    if (next !== null) onNavigate(next);
  };

  const allProcessed = progress.total_pages > 0 && progress.processed_pages === progress.total_pages;

  return (
    <div className="scan-progress" aria-labelledby="scan-progress-heading">
      <h3 id="scan-progress-heading" className="visually-hidden">
        Прогрес сканування словника
      </h3>
      {scanControls}
      <p className="scan-progress-summary" role="status">
        Опрацьовано {formatNumber(progress.processed_pages)} /{" "}
        {formatNumber(progress.total_pages)} сторінок
      </p>
      <div className="progress-track">
        <div
          className="progress-bar"
          style={{ transform: `scaleX(${percent / 100})` }}
        />
      </div>
      <div className="scan-progress-pages">
        {progress.pages.map((page) => (
          <button
            key={page.page_number}
            type="button"
            className={
              page.has_lexemes
                ? "scan-progress-page scan-progress-page--processed"
                : "scan-progress-page"
            }
            aria-current={page.page_number === currentPage ? "page" : undefined}
            title={`Сторінка ${page.page_number}${page.has_lexemes ? " — опрацьована" : ""}`}
            onClick={() => onNavigate(page.page_number)}
          >
            {page.page_number}
          </button>
        ))}
      </div>
      <button
        type="button"
        className="secondary-button"
        onClick={handleJumpToUnprocessed}
        disabled={allProcessed}
      >
        {allProcessed
          ? "Усі сторінки опрацьовано"
          : "Перейти до неопрацьованої сторінки"}
      </button>
    </div>
  );
}
