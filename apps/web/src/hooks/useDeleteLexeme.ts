import { useCallback, useState } from "react";

import { API, apiMessageFrom } from "../api";

export type DeleteLexemeState =
  | { status: "idle" }
  | { status: "deleting" }
  | { status: "error"; message: string };

/** BH-56 AC5: deletes a lexeme; the caller removes it from shared state on success. */
export function useDeleteLexeme(dictionaryId: string) {
  const [state, setState] = useState<DeleteLexemeState>({ status: "idle" });

  const remove = useCallback(
    async (lexemeId: string): Promise<boolean> => {
      setState({ status: "deleting" });
      try {
        await API.lexemes.delete(dictionaryId, lexemeId);
        setState({ status: "idle" });
        return true;
      } catch (error) {
        setState({
          status: "error",
          message: apiMessageFrom(error) ?? "Не вдалося видалити лексему.",
        });
        return false;
      }
    },
    [dictionaryId],
  );

  return { state, remove };
}
