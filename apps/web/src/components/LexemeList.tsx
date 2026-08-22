import { useState } from "react";

import type { LexemesForPageState } from "../hooks/useLexemesForPage";
import type { UpdateLexemeState } from "../hooks/useUpdateLexeme";

/** BH-55/BH-56: the list of lexemes saved on the current page, editable and deletable. */
export function LexemeList({
  lexemesState,
  pageNumber,
  selectedLexemeId,
  onSelectLexeme,
  redrawingLexemeId,
  onStartRedraw,
  onCancelRedraw,
  onSaveText,
  updateState,
  onDelete,
  secondBoxDraftLexemeId = null,
  onStartAddSecondBox,
  onCancelSecondBoxDraft,
  onRemoveSecondBox,
}: {
  lexemesState: LexemesForPageState;
  pageNumber: number;
  selectedLexemeId: string | null;
  onSelectLexeme: (lexemeId: string) => void;
  redrawingLexemeId: string | null;
  onStartRedraw: (lexemeId: string) => void;
  onCancelRedraw: () => void;
  onSaveText: (lexemeId: string, text: string) => void;
  updateState: UpdateLexemeState;
  onDelete: (lexemeId: string) => void;
  secondBoxDraftLexemeId?: string | null;
  onStartAddSecondBox?: (lexemeId: string) => void;
  onCancelSecondBoxDraft?: () => void;
  onRemoveSecondBox?: (lexemeId: string) => void;
}) {
  const [editingLexemeId, setEditingLexemeId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");

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

  const startEditing = (lexemeId: string, currentText: string) => {
    setEditingLexemeId(lexemeId);
    setDraftText(currentText);
  };

  const submitText = (lexemeId: string) => {
    if (!draftText.trim()) return;
    onSaveText(lexemeId, draftText.trim());
    setEditingLexemeId(null);
  };

  const confirmDelete = (lexemeId: string, text: string) => {
    if (window.confirm(`Видалити лексему «${text}»? Цю дію не можна скасувати.`)) {
      onDelete(lexemeId);
    }
  };

  return (
    <ul className="lexeme-list" aria-label="Лексеми на сторінці">
      {lexemesState.lexemes.map((lexeme) => {
        const isEditing = editingLexemeId === lexeme.id;
        const isRedrawing = redrawingLexemeId === lexeme.id;
        const isDraftingSecondBox = secondBoxDraftLexemeId === lexeme.id;
        const hasSecondBox = lexeme.x2 != null;
        return (
          <li key={lexeme.id} className="lexeme-list-row">
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
              {isEditing ? (
                <>
                  <label
                    className="visually-hidden"
                    htmlFor={`lexeme-edit-text-${lexeme.id}`}
                  >
                    Текст лексеми
                  </label>
                  <input
                    id={`lexeme-edit-text-${lexeme.id}`}
                    value={draftText}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => setDraftText(event.target.value)}
                    autoFocus
                  />
                </>
              ) : (
                <span className="lexeme-list-item-text">{lexeme.source_text}</span>
              )}
              <span className="lexeme-list-item-meta">
                Сторінка {pageNumber} · x={Math.round(lexeme.x)}, y=
                {Math.round(lexeme.y)}, {Math.round(lexeme.width)}×
                {Math.round(lexeme.height)}
              </span>
            </button>
            {updateState.status === "error" && isEditing && (
              <p className="field-error" role="alert">
                {updateState.message}
              </p>
            )}
            <div className="lexeme-list-actions">
              {isEditing ? (
                <>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => submitText(lexeme.id)}
                    disabled={updateState.status === "submitting"}
                  >
                    Зберегти
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => setEditingLexemeId(null)}
                  >
                    Скасувати
                  </button>
                </>
              ) : (
                <>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => startEditing(lexeme.id, lexeme.source_text)}
                  >
                    Редагувати текст
                  </button>
                  {isRedrawing ? (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={onCancelRedraw}
                    >
                      Скасувати перемальовування
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onStartRedraw(lexeme.id)}
                    >
                      Перемалювати область
                    </button>
                  )}
                  {isDraftingSecondBox ? (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={onCancelSecondBoxDraft}
                    >
                      Скасувати другу область
                    </button>
                  ) : hasSecondBox ? (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onRemoveSecondBox?.(lexeme.id)}
                    >
                      Видалити другу область
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={() => onStartAddSecondBox?.(lexeme.id)}
                    >
                      Додати другу область
                    </button>
                  )}
                  <button
                    type="button"
                    className="danger-button"
                    onClick={() => confirmDelete(lexeme.id, lexeme.source_text)}
                  >
                    Видалити
                  </button>
                </>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
