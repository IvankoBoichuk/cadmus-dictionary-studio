import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type SyntheticEvent,
} from "react";

import type { LexemeResponse } from "../api";
import { useCreateLexeme } from "../hooks/useCreateLexeme";
import type { UpdateLexemeInput } from "../hooks/useUpdateLexeme";
import {
  isRectLargeEnough,
  normalizeDragRect,
  scaleRect,
  type Point,
  type Rect,
} from "../lexemeGeometry";

type Size = { width: number; height: number };

/** BH-54/BH-55/BH-56: the page image, lexeme drawing, highlighting, and redrawing. */
export function LexemeCanvas({
  dictionaryId,
  pageNumber,
  imageUrl,
  imageAlt,
  lexemes,
  onLexemeCreated,
  selectedLexemeId,
  onSelectLexeme,
  redrawingLexemeId,
  onLexemeRedrawn,
  onCancelRedraw,
  onSubmitUpdate,
}: {
  dictionaryId: string;
  pageNumber: number;
  imageUrl: string;
  imageAlt: string;
  lexemes: LexemeResponse[];
  onLexemeCreated: (lexeme: LexemeResponse) => void;
  selectedLexemeId: string | null;
  onSelectLexeme: (lexemeId: string | null) => void;
  redrawingLexemeId: string | null;
  onLexemeRedrawn: (lexeme: LexemeResponse) => void;
  onCancelRedraw: () => void;
  onSubmitUpdate: (
    lexemeId: string,
    input: UpdateLexemeInput,
  ) => Promise<LexemeResponse | null>;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [naturalSize, setNaturalSize] = useState<Size | null>(null);
  const [displayedSize, setDisplayedSize] = useState<Size | null>(null);
  const [drag, setDrag] = useState<{ start: Point; current: Point } | null>(null);
  const [pendingBox, setPendingBox] = useState<Rect | null>(null);
  const [text, setText] = useState("");

  const { state: createState, submit, reset: resetCreate } = useCreateLexeme(
    dictionaryId,
    pageNumber,
  );

  useEffect(() => {
    function updateDisplayedSize() {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      setDisplayedSize({ width: rect.width, height: rect.height });
    }
    window.addEventListener("resize", updateDisplayedSize);
    return () => window.removeEventListener("resize", updateDisplayedSize);
  }, []);

  const handleImageLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
    if (containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      setDisplayedSize({ width: rect.width, height: rect.height });
    }
  };

  const pointFromEvent = (event: ReactMouseEvent<HTMLDivElement>): Point | null => {
    if (!containerRef.current) return null;
    const rect = containerRef.current.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  const handleMouseDown = (event: ReactMouseEvent<HTMLDivElement>) => {
    const point = pointFromEvent(event);
    if (!point) return;
    setPendingBox(null);
    resetCreate();
    setDrag({ start: point, current: point });
  };

  const handleMouseMove = (event: ReactMouseEvent<HTMLDivElement>) => {
    if (!drag) return;
    const point = pointFromEvent(event);
    if (!point) return;
    setDrag({ start: drag.start, current: point });
  };

  const toNaturalRect = (displayedRect: Rect): Rect | null => {
    if (!naturalSize || !displayedSize || displayedSize.width === 0) return null;
    return scaleRect(displayedRect, naturalSize.width / displayedSize.width);
  };

  const handleMouseUp = () => {
    if (!drag) return;
    const rect = normalizeDragRect(drag.start, drag.current);
    setDrag(null);
    if (!isRectLargeEnough(rect)) return;

    if (redrawingLexemeId) {
      const target = lexemes.find((lexeme) => lexeme.id === redrawingLexemeId);
      const naturalRect = toNaturalRect(rect);
      if (target && naturalRect) {
        void onSubmitUpdate(redrawingLexemeId, {
          source_text: target.source_text,
          ...naturalRect,
        }).then((updated) => {
          if (updated) onLexemeRedrawn(updated);
        });
      }
      return;
    }

    setPendingBox(rect);
    setText("");
  };

  const cancelPending = () => {
    setPendingBox(null);
    setText("");
    resetCreate();
  };

  const handleSubmit = async (
    event: ReactMouseEvent | { preventDefault(): void },
    confirmDuplicate = false,
  ) => {
    event.preventDefault();
    if (!pendingBox) return;
    const naturalRect = toNaturalRect(pendingBox);
    if (!naturalRect) return;
    const created = await submit(
      { source_text: text, ...naturalRect },
      confirmDuplicate,
    );
    if (created) {
      onLexemeCreated(created);
      onSelectLexeme(created.id);
      setPendingBox(null);
      setText("");
    }
  };

  const scale =
    displayedSize && naturalSize && naturalSize.width > 0
      ? displayedSize.width / naturalSize.width
      : null;

  return (
    <div className="lexeme-canvas-wrap">
      {redrawingLexemeId && (
        <p className="lede" role="status">
          Намалюйте нову область для вибраної лексеми.{" "}
          <button type="button" className="secondary-button" onClick={onCancelRedraw}>
            Скасувати перемальовування
          </button>
        </p>
      )}
      <div
        ref={containerRef}
        className="lexeme-canvas"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      >
        <img
          className="page-viewer-image"
          src={imageUrl}
          alt={imageAlt}
          onLoad={handleImageLoad}
          draggable={false}
        />
        {scale !== null &&
          lexemes.map((lexeme) => (
            <div
              key={lexeme.id}
              className={
                lexeme.id === selectedLexemeId
                  ? "lexeme-box lexeme-box--selected"
                  : "lexeme-box"
              }
              title={lexeme.source_text}
              style={{
                left: lexeme.x * scale,
                top: lexeme.y * scale,
                width: lexeme.width * scale,
                height: lexeme.height * scale,
              }}
            />
          ))}
        {drag && (
          <div
            className="lexeme-box lexeme-box--draft"
            style={{
              left: Math.min(drag.start.x, drag.current.x),
              top: Math.min(drag.start.y, drag.current.y),
              width: Math.abs(drag.current.x - drag.start.x),
              height: Math.abs(drag.current.y - drag.start.y),
            }}
          />
        )}
        {pendingBox && (
          <div
            className="lexeme-box lexeme-box--pending"
            style={{
              left: pendingBox.x,
              top: pendingBox.y,
              width: pendingBox.width,
              height: pendingBox.height,
            }}
          />
        )}
      </div>

      {pendingBox && (
        <form className="lexeme-form" onSubmit={handleSubmit}>
          <label htmlFor="lexeme-source-text">Текст лексеми</label>
          <input
            id="lexeme-source-text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            autoFocus
            aria-invalid={Boolean(
              createState.status === "error" && createState.fieldErrors?.source_text,
            )}
          />
          {createState.status === "error" && createState.fieldErrors?.source_text && (
            <p className="field-error" role="alert">
              {createState.fieldErrors.source_text}
            </p>
          )}
          <div className="form-actions">
            <button
              type="submit"
              className="primary-link"
              disabled={createState.status === "submitting" || !text.trim()}
            >
              {createState.status === "submitting" ? "Зберігаємо…" : "Зберегти лексему"}
            </button>
            <button type="button" className="secondary-button" onClick={cancelPending}>
              Скасувати
            </button>
          </div>
          {createState.status === "error" && !createState.fieldErrors && (
            <p className="form-error" role="alert">
              {createState.message}
            </p>
          )}
          {createState.status === "duplicate" && (
            <div className="form-error" role="alert">
              <p>{createState.message}</p>
              <button
                type="button"
                className="secondary-button"
                onClick={(event) => void handleSubmit(event, true)}
              >
                Зберегти попри збіг
              </button>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
