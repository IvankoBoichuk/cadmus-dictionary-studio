import type { LexemesForPageState } from "../hooks/useLexemesForPage";

/** BH-55: the list of lexemes saved on the current page, synced with the canvas. */
export function LexemeList({
  lexemesState,
  pageNumber,
  selectedLexemeId,
  onSelectLexeme,
}: {
  lexemesState: LexemesForPageState;
  pageNumber: number;
  selectedLexemeId: string | null;
  onSelectLexeme: (lexemeId: string) => void;
}) {
  if (lexemesState.status === "loading") {
    return <p role="status">Завантажуємо лексеми…</p>;
  }
  if (lexemesState.status === "error") {
    return (
      <p className="form-error" role="alert">
        {lexemesState.message}
      </p>
    );
  }
  if (lexemesState.lexemes.length === 0) {
    return <p className="lede">На цій сторінці ще немає виділених лексем.</p>;
  }

  return (
    <ul className="lexeme-list" aria-label="Лексеми на сторінці">
      {lexemesState.lexemes.map((lexeme) => (
        <li key={lexeme.id}>
          <button
            type="button"
            className={
              lexeme.id === selectedLexemeId
                ? "lexeme-list-item lexeme-list-item--selected"
                : "lexeme-list-item"
            }
            aria-pressed={lexeme.id === selectedLexemeId}
            onClick={() => onSelectLexeme(lexeme.id)}
          >
            <span className="lexeme-list-item-text">{lexeme.source_text}</span>
            <span className="lexeme-list-item-meta">
              Сторінка {pageNumber} · x={Math.round(lexeme.x)}, y={Math.round(lexeme.y)},
              {" "}
              {Math.round(lexeme.width)}×{Math.round(lexeme.height)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
