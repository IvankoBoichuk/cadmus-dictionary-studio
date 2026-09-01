import {
  Check,
  CheckCheck,
  Columns2,
  FileOutput,
  Pencil,
  SquarePen,
  Trash2,
  X,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import { isFinePointer } from "../interaction";
import type { LexemesForPageState } from "../hooks/useLexemesForPage";
import type { UpdateLexemeState } from "../hooks/useUpdateLexeme";
import { LEXEME_STATUS_LABELS } from "../lexemeStatusLabels";

/** A single compact, tooltip-labelled row action (revealed on hover/focus). */
function RowAction({
  label,
  icon: Icon,
  onClick,
  variant = "secondary",
  disabled,
}: {
  label: string;
  icon: LucideIcon;
  onClick: () => void;
  variant?: "secondary" | "danger";
  disabled?: boolean;
}) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          size="icon-sm"
          variant={variant}
          type="button"
          onClick={onClick}
          disabled={disabled}
          aria-label={label}
        >
          <Icon aria-hidden="true" />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

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
  onMarkComplete,
  onPromoteToEntry,
  promotingLexemeId = null,
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
  onMarkComplete?: (lexemeId: string) => void;
  onPromoteToEntry?: (lexemeId: string) => void;
  promotingLexemeId?: string | null;
}) {
  const [editingLexemeId, setEditingLexemeId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const itemRefs = useRef(new Map<string, HTMLButtonElement>());

  // BH-70: keep the selected row visible in the scrollable list, however it was selected.
  useEffect(() => {
    if (!selectedLexemeId) return;
    itemRefs.current.get(selectedLexemeId)?.scrollIntoView({ block: "nearest" });
  }, [selectedLexemeId]);

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
    <ul
      className="m-0 grid max-h-[70vh] list-none gap-2 overflow-y-auto overscroll-contain p-0 sm:grid-cols-2"
      aria-label="Лексеми на сторінці"
    >
      {lexemesState.lexemes.map((lexeme) => {
        const isEditing = editingLexemeId === lexeme.id;
        const isRedrawing = redrawingLexemeId === lexeme.id;
        const isDraftingSecondBox = secondBoxDraftLexemeId === lexeme.id;
        const hasSecondBox = lexeme.x2 != null;
        const isComplete = lexeme.status === "complete";
        return (
          <li key={lexeme.id} className="group grid content-start gap-[0.35rem]">
            <button
              type="button"
              ref={(element) => {
                if (element) itemRefs.current.set(lexeme.id, element);
                else itemRefs.current.delete(lexeme.id);
              }}
              className={cn(
                "grid w-full gap-[0.2rem] rounded-[0.5rem] border bg-surface px-3 py-[0.6rem] text-left text-foreground",
                lexeme.id === selectedLexemeId &&
                  "border-selected bg-[rgb(185_28_28_/_8%)]",
              )}
              aria-pressed={lexeme.id === selectedLexemeId}
              onClick={() => onSelectLexeme(lexeme.id)}
            >
              {isEditing ? (
                <>
                  <label
                    className="sr-only"
                    htmlFor={`lexeme-edit-text-${lexeme.id}`}
                  >
                    Текст лексеми
                  </label>
                  <Input
                    className="min-h-[2.2rem] rounded-[0.4rem] px-2 py-[0.35rem] font-[650]"
                    id={`lexeme-edit-text-${lexeme.id}`}
                    name="source_text"
                    value={draftText}
                    onClick={(event) => event.stopPropagation()}
                    onChange={(event) => setDraftText(event.target.value)}
                    autoFocus={isFinePointer()}
                  />
                </>
              ) : (
                <span className="font-[650] [overflow-wrap:anywhere]">
                  {lexeme.source_text}
                </span>
              )}
              <span className="text-[0.8rem] text-muted-foreground tabular-nums">
                Сторінка {pageNumber} · x={Math.round(lexeme.x)}, y=
                {Math.round(lexeme.y)}, {Math.round(lexeme.width)}×
                {Math.round(lexeme.height)}
                {" · "}
                <Badge
                  className="ml-2"
                  variant={isComplete ? "secondary" : "info"}
                >
                  {LEXEME_STATUS_LABELS[lexeme.status]}
                </Badge>
              </span>
            </button>
            {updateState.status === "error" && isEditing && (
              <p className="field-error" role="alert">
                {updateState.message}
              </p>
            )}
            <div
              className={cn(
                "flex flex-wrap gap-1 transition-opacity",
                "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100",
                "[@media(hover:none)]:opacity-100",
                (isEditing || isRedrawing || isDraftingSecondBox) && "opacity-100",
              )}
            >
              {isComplete ? (
                <>
                  <p className="lede m-0">
                    Лексема завершена — редагування заблоковане.
                  </p>
                  <RowAction
                    label={
                      promotingLexemeId === lexeme.id
                        ? "Створюємо статтю…"
                        : "Створити статтю зі структурою"
                    }
                    icon={FileOutput}
                    onClick={() => onPromoteToEntry?.(lexeme.id)}
                    disabled={promotingLexemeId === lexeme.id}
                  />
                </>
              ) : isEditing ? (
                <>
                  <RowAction
                    label="Зберегти"
                    icon={Check}
                    onClick={() => submitText(lexeme.id)}
                    disabled={updateState.status === "submitting"}
                  />
                  <RowAction
                    label="Скасувати"
                    icon={X}
                    onClick={() => setEditingLexemeId(null)}
                  />
                </>
              ) : (
                <>
                  <RowAction
                    label="Редагувати текст"
                    icon={Pencil}
                    onClick={() => startEditing(lexeme.id, lexeme.source_text)}
                  />
                  {isRedrawing ? (
                    <RowAction
                      label="Скасувати перемальовування"
                      icon={X}
                      onClick={onCancelRedraw}
                    />
                  ) : (
                    <RowAction
                      label="Перемалювати область"
                      icon={SquarePen}
                      onClick={() => onStartRedraw(lexeme.id)}
                    />
                  )}
                  {isDraftingSecondBox ? (
                    <RowAction
                      label="Скасувати другу область"
                      icon={X}
                      onClick={() => onCancelSecondBoxDraft?.()}
                    />
                  ) : hasSecondBox ? (
                    <RowAction
                      label="Видалити другу область"
                      icon={Columns2}
                      variant="danger"
                      onClick={() => onRemoveSecondBox?.(lexeme.id)}
                    />
                  ) : (
                    <RowAction
                      label="Додати другу область"
                      icon={Columns2}
                      onClick={() => onStartAddSecondBox?.(lexeme.id)}
                    />
                  )}
                  <RowAction
                    label="Позначити завершеною"
                    icon={CheckCheck}
                    onClick={() => onMarkComplete?.(lexeme.id)}
                  />
                  <RowAction
                    label="Видалити"
                    icon={Trash2}
                    variant="danger"
                    onClick={() => confirmDelete(lexeme.id, lexeme.source_text)}
                  />
                </>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
