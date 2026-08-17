import { useCallback, useState } from "react";

import {
  API,
  apiMessageFrom,
  type SettlementImportCommitResponse,
  type SettlementImportPreviewResponse,
  type SettlementMappingResponse,
} from "../api";

export type SettlementImportState =
  | { status: "idle" }
  | { status: "previewing" }
  | { status: "previewed"; preview: SettlementImportPreviewResponse }
  | { status: "committing"; preview: SettlementImportPreviewResponse }
  | { status: "done"; outcome: SettlementImportCommitResponse }
  | { status: "error"; message: string };

/**
 * Drives BH-30's upload-then-preview-then-confirm bulk import workflow for
 * geographic labels. `onImported` merges newly persisted rows into the
 * caller's list. Imported rows are always created as `status="unresolved"`
 * -- matching a modern settlement happens afterward, one row at a time.
 */
export function useSettlementImport(
  dictionaryId: string,
  onImported: (items: SettlementMappingResponse[]) => void,
) {
  const [state, setState] = useState<SettlementImportState>({ status: "idle" });

  const preview = useCallback(
    async (file: File) => {
      setState({ status: "previewing" });
      try {
        const result = await API.settlements.importPreview(dictionaryId, file);
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
    async (preview: SettlementImportPreviewResponse) => {
      setState({ status: "committing", preview });
      const rows = preview.rows
        .filter((row) => row.valid)
        .flatMap((row) => (row.input ? [row.input] : []));
      try {
        const outcome = await API.settlements.importCommit(dictionaryId, { rows });
        onImported(outcome.imported);
        setState({ status: "done", outcome });
      } catch (error) {
        setState({
          status: "error",
          message: apiMessageFrom(error) ?? "Не вдалося імпортувати географічні мітки.",
        });
      }
    },
    [dictionaryId, onImported],
  );

  const reset = useCallback(() => setState({ status: "idle" }), []);

  return { state, preview, commit, reset } as const;
}
