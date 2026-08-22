import { useCallback, useState } from "react";

import {
  API,
  apiMessageFrom,
  duplicateLexemeFrom,
  fieldErrorsFrom,
  type LexemeResponse,
} from "../api";

export type CreateLexemeInput = {
  source_text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  origin?: "manual" | "ocr";
  x2?: number | null;
  y2?: number | null;
  width2?: number | null;
  height2?: number | null;
};

export type CreateLexemeState =
  | { status: "idle" }
  | { status: "submitting" }
  | { status: "duplicate"; message: string; existingLexemeId: string }
  | { status: "error"; fieldErrors?: Record<string, string>; message: string };

/** BH-54: submits a manually drawn lexeme, mapping duplicate/field errors (AC1-AC6). */
export function useCreateLexeme(dictionaryId: string, pageNumber: number) {
  const [state, setState] = useState<CreateLexemeState>({ status: "idle" });

  const submit = useCallback(
    async (
      input: CreateLexemeInput,
      confirmDuplicate = false,
    ): Promise<LexemeResponse | null> => {
      setState({ status: "submitting" });
      try {
        const lexeme = await API.lexemes.create(dictionaryId, pageNumber, {
          ...input,
          origin: input.origin ?? "manual",
          confirm_duplicate: confirmDuplicate,
        });
        setState({ status: "idle" });
        return lexeme;
      } catch (error) {
        const duplicate = duplicateLexemeFrom(error);
        if (duplicate) {
          setState({
            status: "duplicate",
            message: duplicate.message,
            existingLexemeId: duplicate.existing_lexeme_id,
          });
          return null;
        }
        const fieldErrors = fieldErrorsFrom(error);
        setState({
          status: "error",
          fieldErrors,
          message:
            apiMessageFrom(error) ??
            (fieldErrors
              ? "Перевірте виділену область і текст."
              : "Не вдалося зберегти лексему. Спробуйте пізніше."),
        });
        return null;
      }
    },
    [dictionaryId, pageNumber],
  );

  const reset = useCallback(() => setState({ status: "idle" }), []);

  return { state, submit, reset };
}
