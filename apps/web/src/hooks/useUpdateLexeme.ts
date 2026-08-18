import { useCallback, useState } from "react";

import { API, apiMessageFrom, fieldErrorsFrom, type LexemeResponse } from "../api";

export type UpdateLexemeInput = {
  source_text: string;
  x: number;
  y: number;
  width: number;
  height: number;
};

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
