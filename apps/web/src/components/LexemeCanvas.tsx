import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type SyntheticEvent,
} from "react";

import { useCreateLexeme } from "../hooks/useCreateLexeme";
import { useLexemesForPage } from "../hooks/useLexemesForPage";
import {
  isRectLargeEnough,
  normalizeDragRect,
  scaleRect,
  type Point,
  type Rect,
} from "../lexemeGeometry";

type Size = { width: number; height: number };

/** BH-54: the page image plus manual lexeme drawing and highlighting (AC1-AC7). */
export function LexemeCanvas({
  dictionaryId,
  pageNumber,
  imageUrl,
  imageAlt,
}: {
  dictionaryId: string;
  pageNumber: number;
  imageUrl: string;
  imageAlt: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [naturalSize, setNaturalSize] = useState<Size | null>(null);
  const [displayedSize, setDisplayedSize] = useState<Size | null>(null);
  const [drag, setDrag] = useState<{ start: Point; current: Point } | null>(null);
  const [pendingBox, setPendingBox] = useState<Rect | null>(null);
  const [text, setText] = useState("");

  const { state: lexemesState, addLexeme } = useLexemesForPage(dictionaryId, pageNumber);
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

  const handleMouseUp = () => {
    if (!drag) return;
    const rect = normalizeDragRect(drag.start, drag.current);
    setDrag(null);
    if (isRectLargeEnough(rect)) {
      setPendingBox(rect);
      setText("");
    }
  };

  const cancelPending = () => {
    setPendingBox(null);
    setText("");
    resetCreate();
  };

  const toNaturalRect = (displayedRect: Rect): Rect | null => {
    if (!naturalSize || !displayedSize || displayedSize.width === 0) return null;
    return scaleRect(displayedRect, naturalSize.width / displayedSize.width);
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
      addLexeme(created);
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
          lexemesState.status === "loaded" &&
          lexemesState.lexemes.map((lexeme) => (
            <div
              key={lexeme.id}
              className="lexeme-box"
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

      {lexemesState.status === "error" && (
        <p className="form-error" role="alert">
          {lexemesState.message}
        </p>
      )}

      {pendingBox && (
        <form className="lexeme-form" onSubmit={handleSubmit}>
          <label htmlFor="lexeme-source-text">Текст лексеми</label>
          <input
            id="lexeme-source-text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            autoFocus
            aria-invalid={Boolean(createState.status === "error" && createState.fieldErrors?.source_text)}
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
