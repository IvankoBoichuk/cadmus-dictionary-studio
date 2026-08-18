import { useCallback, useEffect, useState } from "react";

import { API, apiMessageFrom, isAbortError, type LexemeResponse } from "../api";

export type LexemesForPageState =
  | { status: "loading" }
  | { status: "loaded"; lexemes: LexemeResponse[] }
  | { status: "error"; message: string };

/** BH-54 AC7: loads the lexemes manually selected on one page. */
export function useLexemesForPage(dictionaryId: string, pageNumber: number) {
  const [state, setState] = useState<LexemesForPageState>({ status: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    API.lexemes.list(dictionaryId, pageNumber, { signal: controller.signal }).then(
      (lexemes) => setState({ status: "loaded", lexemes }),
      (error: unknown) => {
        if (isAbortError(error)) return;
        setState({
          status: "error",
          message:
            apiMessageFrom(error) ?? "Не вдалося завантажити лексеми. Спробуйте пізніше.",
        });
      },
    );
    return () => controller.abort();
  }, [dictionaryId, pageNumber]);

  const addLexeme = useCallback((lexeme: LexemeResponse) => {
    setState((current) =>
      current.status === "loaded"
        ? { status: "loaded", lexemes: [...current.lexemes, lexeme] }
        : { status: "loaded", lexemes: [lexeme] },
    );
  }, []);

  return { state, addLexeme };
}
