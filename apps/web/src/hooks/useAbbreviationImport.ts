import { useCallback, useState } from "react";

import {
  API,
  apiMessageFrom,
  type AbbreviationResponse,
  type ImportCommitResponse,
  type ImportPreviewResponse,
} from "../api";

export type AbbreviationImportState =
  | { status: "idle" }
  | { status: "previewing" }
  | { status: "previewed"; preview: ImportPreviewResponse }
  | { status: "committing"; preview: ImportPreviewResponse }
  | { status: "done"; outcome: ImportCommitResponse }
  | { status: "error"; message: string };

/**
 * Drives BH-29's upload-then-preview-then-confirm bulk import workflow
 * (AC5, AC6). `onImported` merges newly persisted rows into the caller's list.
 */
export function useAbbreviationImport(
  dictionaryId: string,
  onImported: (items: AbbreviationResponse[]) => void,
) {
  const [state, setState] = useState<AbbreviationImportState>({ status: "idle" });

  const preview = useCallback(
    async (file: File) => {
      setState({ status: "previewing" });
      try {
        const result = await API.abbreviations.importPreview(dictionaryId, file);
        setState({ status: "previewed", preview: result });
      } catch (error) {
        setState({
          status: "error",
          message: apiMessageFrom(error) ?? "Не вдалося розібрати файл імпорту.",
        });
      }
    },
    [dictionaryId],
  );

  const commit = useCallback(
    async (preview: ImportPreviewResponse) => {
      setState({ status: "committing", preview });
      const rows = preview.rows
        .filter((row) => row.valid)
        .flatMap((row) => (row.input ? [row.input] : []));
      try {
        const outcome = await API.abbreviations.importCommit(dictionaryId, { rows });
        onImported(outcome.imported);
        setState({ status: "done", outcome });
      } catch (error) {
        setState({
          status: "error",
          message: apiMessageFrom(error) ?? "Не вдалося імпортувати скорочення.",
        });
      }
    },
    [dictionaryId, onImported],
  );

  const reset = useCallback(() => setState({ status: "idle" }), []);

  return { state, preview, commit, reset } as const;
}
