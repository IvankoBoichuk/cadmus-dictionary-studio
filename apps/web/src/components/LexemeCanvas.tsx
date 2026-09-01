import {
  useEffect,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type RefObject,
  type SyntheticEvent,
} from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

import type { LexemeResponse, LexemeSuggestion } from "../api";
import type { CanvasMode } from "../canvasTools";
import { isFinePointer, scrollIntoViewOptions } from "../interaction";
import { useCreateLexeme } from "../hooks/useCreateLexeme";
import { lexemeToUpdateInput, type UpdateLexemeInput } from "../hooks/useUpdateLexeme";
import {
  HANDLES,
  isRectLargeEnough,
  normalizeDragRect,
  resizeRect,
  scaleRect,
  type HandleId,
  type Point,
  type Rect,
} from "../lexemeGeometry";

type Size = { width: number; height: number };

/** Per-corner/edge offsets + resize cursor for a selected box's handles. */
const HANDLE_CLASSES: Record<HandleId, string> = {
  nw: "left-[-5px] top-[-5px] cursor-nwse-resize",
  n: "left-1/2 top-[-5px] -translate-x-1/2 cursor-ns-resize",
  ne: "right-[-5px] top-[-5px] cursor-nesw-resize",
  w: "left-[-5px] top-1/2 -translate-y-1/2 cursor-ew-resize",
  e: "right-[-5px] top-1/2 -translate-y-1/2 cursor-ew-resize",
  sw: "left-[-5px] bottom-[-5px] cursor-nesw-resize",
  s: "left-1/2 bottom-[-5px] -translate-x-1/2 cursor-ns-resize",
  se: "right-[-5px] bottom-[-5px] cursor-nwse-resize",
};

type HandleDragState = {
  box: 1 | 2;
  handle: HandleId;
  start: Point;
  current: Point;
  original: Rect;
};

function box1Rect(lexeme: LexemeResponse): Rect {
  return { x: lexeme.x, y: lexeme.y, width: lexeme.width, height: lexeme.height };
}

function box2Rect(lexeme: LexemeResponse): Rect | null {
  if (
    lexeme.x2 == null ||
    lexeme.y2 == null ||
    lexeme.width2 == null ||
    lexeme.height2 == null
  ) {
    return null;
  }
  return { x: lexeme.x2, y: lexeme.y2, width: lexeme.width2, height: lexeme.height2 };
}

/** One lexeme's box: clickable to select, with resize handles once selected. */
function LexemeBox({
  rect,
  selected,
  title,
  showHandles,
  onSelect,
  onHandleMouseDown,
  boxRef,
}: {
  rect: Rect;
  selected: boolean;
  title: string;
  showHandles: boolean;
  onSelect: () => void;
  onHandleMouseDown: (handle: HandleId, event: ReactMouseEvent<HTMLDivElement>) => void;
  boxRef?: RefObject<HTMLDivElement | null>;
}) {
  return (
    <div
      ref={boxRef}
      // Focusable programmatically (not via Tab) so BH-70 can move assistive focus here.
      tabIndex={selected ? -1 : undefined}
      className={cn(
        "pointer-events-auto absolute cursor-pointer border-2 border-lexeme bg-[rgb(217_119_6_/_15%)]",
        selected &&
          "border-[3px] border-selected bg-[rgb(185_28_28_/_18%)]",
      )}
      title={title}
      onMouseDown={(event) => event.stopPropagation()}
      onClick={onSelect}
      style={{ left: rect.x, top: rect.y, width: rect.width, height: rect.height }}
    >
      {showHandles &&
        HANDLES.map((handle) => (
          <div
            key={handle}
            data-handle={handle}
            className={cn(
              "pointer-events-auto absolute size-[10px] rounded-[2px] border border-white bg-selected",
              HANDLE_CLASSES[handle],
            )}
            onMouseDown={(event) => onHandleMouseDown(handle, event)}
          />
        ))}
    </div>
  );
}

/** BH-54/55/56: the page image, lexeme drawing, highlighting, and editing. */
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
  suggestions = [],
  onAcceptSuggestion,
  secondBoxDraftLexemeId = null,
  onSecondBoxDrawn,
  onCancelSecondBoxDraft,
  mode = "select",
  zoom = 1,
  onEraseLexeme,
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
  suggestions?: LexemeSuggestion[];
  onAcceptSuggestion?: (suggestion: LexemeSuggestion) => void;
  secondBoxDraftLexemeId?: string | null;
  onSecondBoxDrawn?: (lexeme: LexemeResponse) => void;
  onCancelSecondBoxDraft?: () => void;
  mode?: CanvasMode;
  zoom?: number;
  onEraseLexeme?: (lexemeId: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [naturalSize, setNaturalSize] = useState<Size | null>(null);
  const [displayedSize, setDisplayedSize] = useState<Size | null>(null);
  const [fitWidth, setFitWidth] = useState<number | null>(null);
  const [drag, setDrag] = useState<{ start: Point; current: Point } | null>(null);
  const [pendingBox, setPendingBox] = useState<Rect | null>(null);
  const [text, setText] = useState("");
  const [pendingSuggestion, setPendingSuggestion] = useState<LexemeSuggestion | null>(
    null,
  );
  const [handleDrag, setHandleDrag] = useState<HandleDragState | null>(null);
  const selectedBoxRef = useRef<HTMLDivElement>(null);

  const { state: createState, submit, reset: resetCreate } = useCreateLexeme(
    dictionaryId,
    pageNumber,
  );

  // The image is rendered at `fitWidth * zoom` px wide; the frame scrolls when
  // that exceeds the panel. `displayedSize` (and thus `scale`) is derived from
  // it, so every `scaleRect` call downstream stays correct as the user zooms.
  useEffect(() => {
    function measureFit() {
      if (scrollRef.current) {
        setFitWidth(scrollRef.current.getBoundingClientRect().width);
      }
    }
    measureFit();
    window.addEventListener("resize", measureFit);
    return () => window.removeEventListener("resize", measureFit);
  }, []);

  useEffect(() => {
    if (fitWidth === null || !naturalSize || naturalSize.width === 0) return;
    const width = fitWidth * zoom;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- derived layout sync
    setDisplayedSize({
      width,
      height: width * (naturalSize.height / naturalSize.width),
    });
  }, [fitWidth, zoom, naturalSize]);

  const handleImageLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    setNaturalSize({ width: image.naturalWidth, height: image.naturalHeight });
    if (scrollRef.current) {
      setFitWidth(scrollRef.current.getBoundingClientRect().width);
    }
  };

  const pointFromEvent = (event: ReactMouseEvent<HTMLDivElement>): Point | null => {
    if (!containerRef.current) return null;
    const rect = containerRef.current.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };

  const toNaturalRect = (displayedRect: Rect): Rect | null => {
    if (!naturalSize || !displayedSize || displayedSize.width === 0) return null;
    return scaleRect(displayedRect, naturalSize.width / displayedSize.width);
  };

  const drawingAllowed =
    mode === "draw" ||
    redrawingLexemeId !== null ||
    secondBoxDraftLexemeId !== null;

  const handleMouseDown = (event: ReactMouseEvent<HTMLDivElement>) => {
    const point = pointFromEvent(event);
    if (!point) return;
    setPendingBox(null);
    setPendingSuggestion(null);
    resetCreate();
    if (
      selectedLexemeId !== null &&
      redrawingLexemeId === null &&
      secondBoxDraftLexemeId === null
    ) {
      onSelectLexeme(null);
    }
    if (drawingAllowed) setDrag({ start: point, current: point });
  };

  const handleMouseMove = (event: ReactMouseEvent<HTMLDivElement>) => {
    const point = pointFromEvent(event);
    if (!point) return;
    if (handleDrag) {
      setHandleDrag({ ...handleDrag, current: point });
      return;
    }
    if (!drag) return;
    setDrag({ start: drag.start, current: point });
  };

  const handleMouseUp = () => {
    if (handleDrag) {
      const lexeme = lexemes.find((candidate) => candidate.id === selectedLexemeId);
      const finalRect = resizeRect(
        handleDrag.original,
        handleDrag.handle,
        handleDrag.current.x - handleDrag.start.x,
        handleDrag.current.y - handleDrag.start.y,
      );
      const naturalRect = toNaturalRect(finalRect);
      const { box } = handleDrag;
      setHandleDrag(null);
      if (lexeme && naturalRect && selectedLexemeId) {
        const overrides =
          box === 1
            ? {
                x: naturalRect.x,
                y: naturalRect.y,
                width: naturalRect.width,
                height: naturalRect.height,
              }
            : {
                x2: naturalRect.x,
                y2: naturalRect.y,
                width2: naturalRect.width,
                height2: naturalRect.height,
              };
        void onSubmitUpdate(selectedLexemeId, {
          ...lexemeToUpdateInput(lexeme),
          ...overrides,
        }).then((updated) => {
          if (updated) onLexemeRedrawn(updated);
        });
      }
      return;
    }

    if (!drag) return;
    const rect = normalizeDragRect(drag.start, drag.current);
    setDrag(null);
    if (!isRectLargeEnough(rect)) return;

    if (redrawingLexemeId) {
      const target = lexemes.find((lexeme) => lexeme.id === redrawingLexemeId);
      const naturalRect = toNaturalRect(rect);
      if (target && naturalRect) {
        void onSubmitUpdate(redrawingLexemeId, {
          ...lexemeToUpdateInput(target),
          x: naturalRect.x,
          y: naturalRect.y,
          width: naturalRect.width,
          height: naturalRect.height,
        }).then((updated) => {
          if (updated) onLexemeRedrawn(updated);
        });
      }
      return;
    }

    if (secondBoxDraftLexemeId) {
      const target = lexemes.find((lexeme) => lexeme.id === secondBoxDraftLexemeId);
      const naturalRect = toNaturalRect(rect);
      if (target && naturalRect) {
        void onSubmitUpdate(secondBoxDraftLexemeId, {
          ...lexemeToUpdateInput(target),
          x2: naturalRect.x,
          y2: naturalRect.y,
          width2: naturalRect.width,
          height2: naturalRect.height,
        }).then((updated) => {
          if (updated) onSecondBoxDrawn?.(updated);
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
    setPendingSuggestion(null);
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
      {
        source_text: text,
        ...naturalRect,
        origin: pendingSuggestion ? "ocr" : "manual",
      },
      confirmDuplicate,
    );
    if (created) {
      onLexemeCreated(created);
      onSelectLexeme(created.id);
      if (pendingSuggestion) onAcceptSuggestion?.(pendingSuggestion);
      setPendingBox(null);
      setText("");
      setPendingSuggestion(null);
    }
  };

  const scale =
    displayedSize && naturalSize && naturalSize.width > 0
      ? displayedSize.width / naturalSize.width
      : null;

  // BH-70: once the selected lexeme's box is on screen, scroll and focus it --
  // `scale` becomes non-null only once the image (and boxes) have actually mounted.
  useEffect(() => {
    if (!selectedLexemeId || !selectedBoxRef.current) return;
    selectedBoxRef.current.scrollIntoView(
      scrollIntoViewOptions({ block: "center", inline: "center" }),
    );
    selectedBoxRef.current.focus({ preventScroll: true });
  }, [selectedLexemeId, scale]);

  const handleAcceptSuggestion = (suggestion: LexemeSuggestion) => {
    if (!scale) return;
    setDrag(null);
    resetCreate();
    setPendingBox(
      scaleRect(
        {
          x: suggestion.x,
          y: suggestion.y,
          width: suggestion.width,
          height: suggestion.height,
        },
        scale,
      ),
    );
    setText(suggestion.source_text);
    setPendingSuggestion(suggestion);
  };

  const startHandleDrag = (
    lexeme: LexemeResponse,
    box: 1 | 2,
    handle: HandleId,
    event: ReactMouseEvent<HTMLDivElement>,
  ) => {
    event.stopPropagation();
    const point = pointFromEvent(event);
    if (!point || !scale) return;
    const natural = box === 1 ? box1Rect(lexeme) : box2Rect(lexeme);
    if (!natural) return;
    setHandleDrag({
      box,
      handle,
      start: point,
      current: point,
      original: scaleRect(natural, scale),
    });
  };

  const cursorClass = drawingAllowed
    ? "cursor-crosshair"
    : mode === "erase"
      ? "cursor-pointer"
      : "cursor-default";

  const handleBoxActivate = (lexemeId: string) => {
    if (mode === "erase") onEraseLexeme?.(lexemeId);
    else onSelectLexeme(lexemeId);
  };

  return (
    <div className="grid gap-3">
      {redrawingLexemeId && (
        <p className="lede" role="status">
          Намалюйте нову область для вибраної лексеми.{" "}
          <Button variant="secondary" type="button" onClick={onCancelRedraw}>
            Скасувати перемальовування
          </Button>
        </p>
      )}
      {secondBoxDraftLexemeId && (
        <p className="lede" role="status">
          Намалюйте другу область для вибраної лексеми (наприклад, продовження в іншій
          колонці).{" "}
          <Button
            variant="secondary"
            type="button"
            onClick={onCancelSecondBoxDraft}
          >
            Скасувати
          </Button>
        </p>
      )}
      <div
        ref={scrollRef}
        className="max-h-[80vh] w-full overflow-auto overscroll-contain rounded-[0.75rem] border bg-surface"
      >
        <div
          ref={containerRef}
          className={cn("relative w-max select-none", cursorClass)}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          <img
            className="block"
            style={
              displayedSize ? { width: `${displayedSize.width}px` } : undefined
            }
            src={imageUrl}
            alt={imageAlt}
            onLoad={handleImageLoad}
            draggable={false}
          />
        {scale !== null &&
          lexemes
            .filter((lexeme) => selectedLexemeId === null || lexeme.id === selectedLexemeId)
            .map((lexeme) => {
              const isSelected = lexeme.id === selectedLexemeId;
              const isFullyRedrawing = lexeme.id === redrawingLexemeId;
              const isDraftingSecondBox = lexeme.id === secondBoxDraftLexemeId;
              const isComplete = lexeme.status === "complete";
              const box1Displayed =
                isSelected && handleDrag?.box === 1
                  ? resizeRect(
                      handleDrag.original,
                      handleDrag.handle,
                      handleDrag.current.x - handleDrag.start.x,
                      handleDrag.current.y - handleDrag.start.y,
                    )
                  : scaleRect(box1Rect(lexeme), scale);
              const naturalBox2 = box2Rect(lexeme);
              const box2Displayed =
                naturalBox2 === null
                  ? null
                  : isSelected && handleDrag?.box === 2
                    ? resizeRect(
                        handleDrag.original,
                        handleDrag.handle,
                        handleDrag.current.x - handleDrag.start.x,
                        handleDrag.current.y - handleDrag.start.y,
                      )
                    : scaleRect(naturalBox2, scale);
              return (
                <div key={lexeme.id}>
                  {!isFullyRedrawing && (
                    <LexemeBox
                      rect={box1Displayed}
                      selected={isSelected}
                      title={lexeme.source_text}
                      showHandles={isSelected && !isDraftingSecondBox && !isComplete}
                      onSelect={() => handleBoxActivate(lexeme.id)}
                      onHandleMouseDown={(handle, event) =>
                        startHandleDrag(lexeme, 1, handle, event)
                      }
                      boxRef={isSelected ? selectedBoxRef : undefined}
                    />
                  )}
                  {box2Displayed && !isDraftingSecondBox && (
                    <LexemeBox
                      rect={box2Displayed}
                      selected={isSelected}
                      title={lexeme.source_text}
                      showHandles={isSelected && !isComplete}
                      onSelect={() => handleBoxActivate(lexeme.id)}
                      onHandleMouseDown={(handle, event) =>
                        startHandleDrag(lexeme, 2, handle, event)
                      }
                    />
                  )}
                </div>
              );
            })}
        {scale !== null &&
          suggestions
            .filter((suggestion) => suggestion !== pendingSuggestion)
            .map((suggestion, index) => (
              <button
                type="button"
                key={`${suggestion.x}-${suggestion.y}-${index}`}
                className="pointer-events-auto absolute cursor-pointer rounded-none border-2 border-dashed border-lexeme-suggestion bg-[rgb(37_99_235_/_10%)] p-0 hover:bg-[rgb(37_99_235_/_22%)]"
                title={suggestion.source_text}
                aria-label={`Прийняти запропоноване слово «${suggestion.source_text}»`}
                onMouseDown={(event) => event.stopPropagation()}
                onClick={() => handleAcceptSuggestion(suggestion)}
                style={{
                  left: suggestion.x * scale,
                  top: suggestion.y * scale,
                  width: suggestion.width * scale,
                  height: suggestion.height * scale,
                }}
              />
            ))}
        {drag && (
          <div
            className="pointer-events-none absolute border-2 border-dashed border-primary bg-[rgb(36_88_71_/_12%)]"
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
            className="pointer-events-none absolute border-2 border-primary bg-[rgb(36_88_71_/_18%)]"
            style={{
              left: pendingBox.x,
              top: pendingBox.y,
              width: pendingBox.width,
              height: pendingBox.height,
            }}
          />
        )}
        </div>
      </div>

      {pendingBox && (
        <form
          className="grid w-[min(100%,24rem)] gap-2"
          onSubmit={handleSubmit}
        >
          <label htmlFor="lexeme-source-text">Текст лексеми</label>
          <Input
            className="min-h-[2.6rem] rounded-[0.5rem] px-[0.65rem] py-2"
            id="lexeme-source-text"
            name="source_text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            autoFocus={isFinePointer()}
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
            <Button
              type="submit"
              className="mt-4 px-[1.1rem] py-3"
              disabled={createState.status === "submitting" || !text.trim()}
            >
              {createState.status === "submitting" ? "Зберігаємо…" : "Зберегти лексему"}
            </Button>
            <Button variant="secondary" type="button" onClick={cancelPending}>
              Скасувати
            </Button>
          </div>
          {createState.status === "error" && !createState.fieldErrors && (
            <p className="form-error" role="alert">
              {createState.message}
            </p>
          )}
          {createState.status === "duplicate" && (
            <div className="form-error" role="alert">
              <p>{createState.message}</p>
              <Button
                variant="secondary"
                type="button"
                onClick={(event) => void handleSubmit(event, true)}
              >
                Зберегти попри збіг
              </Button>
            </div>
          )}
        </form>
      )}
    </div>
  );
}
