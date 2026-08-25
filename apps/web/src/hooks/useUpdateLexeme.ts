import { useCallback, useState } from "react";

import {
  API,
  apiMessageFrom,
  fieldErrorsFrom,
  type LexemeResponse,
  type LexemeStatus,
} from "../api";

export type UpdateLexemeInput = {
  source_text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  x2?: number | null;
  y2?: number | null;
  width2?: number | null;
  height2?: number | null;
  status?: LexemeStatus | null;
};

/**
 * Carries a lexeme's *current* box state into an update call so a partial
 * edit (text only, box1 only, box2 only) never silently wipes the fields
 * it didn't mean to touch -- notably an existing second box.
 */
export function lexemeToUpdateInput(lexeme: LexemeResponse): UpdateLexemeInput {
  return {
    source_text: lexeme.source_text,
    x: lexeme.x,
    y: lexeme.y,
    width: lexeme.width,
    height: lexeme.height,
    x2: lexeme.x2 ?? null,
    y2: lexeme.y2 ?? null,
    width2: lexeme.width2 ?? null,
    height2: lexeme.height2 ?? null,
  };
}

export type UpdateLexemeState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "error"; fieldErrors?: Record<string, string>; message: string };

/** BH-56: submits a lexeme text/bounding-box edit, saved instantly (AC4). */
export function useUpdateLexeme(dictionaryId: string) {
  const [state, setState] = useState<UpdateLexemeState>({ status: "idle" });

  const submit = useCallback(
    async (lexemeId: string, input: UpdateLexemeInput): Promise<LexemeResponse | null> => {
      setState({ status: "submitting" });
      try {
        const updated = await API.lexemes.update(dictionaryId, lexemeId, input);
        setState({ status: "idle" });
        return updated;
      } catch (error) {
        const fieldErrors = fieldErrorsFrom(error);
        setState({
          status: "error",
          fieldErrors,
          message:
            apiMessageFrom(error) ??
            (fieldErrors
              ? "Перевірте текст і виділену область."
              : "Не вдалося зберегти зміни. Спробуйте пізніше."),
        });
        return null;
      }
    },
    [dictionaryId],
  );

  const reset = useCallback(() => setState({ status: "idle" }), []);

  return { state, submit, reset };
}
