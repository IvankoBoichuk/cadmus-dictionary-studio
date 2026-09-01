import { useCallback, useState } from "react";

import { API, ApiError, apiMessageFrom } from "../api";

type Kind = "approve" | "sendBack";

export type ReviewDecisionState =
  | { status: "idle" }
  | { status: "pending"; entryId: string; kind: Kind }
  | { status: "error"; entryId: string; message: string };

const SCHEMA_MISMATCH_MESSAGE =
  "Стаття не відповідає схемі — відкрийте її, щоб виправити поля.";

/**
 * Approve / send-back mutations for one review-queue row. On success the
 * caller-supplied `onDone` refreshes the queue (the row leaves it).
 */
export function useReviewDecision(onDone: () => void) {
  const [state, setState] = useState<ReviewDecisionState>({ status: "idle" });

  const run = useCallback(
    async (kind: Kind, entryId: string, note: string): Promise<boolean> => {
      setState({ status: "pending", entryId, kind });
      const trimmed = note.trim();
      const body = trimmed ? { note: trimmed } : {};
      try {
        if (kind === "approve") await API.review.approve(entryId, body);
        else await API.review.sendBack(entryId, body);
        setState({ status: "idle" });
        onDone();
        return true;
      } catch (error) {
        const schemaMismatch =
          error instanceof ApiError && error.status === 422;
        setState({
          status: "error",
          entryId,
          message: schemaMismatch
            ? SCHEMA_MISMATCH_MESSAGE
            : (apiMessageFrom(error) ?? "Не вдалося виконати дію."),
        });
        return false;
      }
    },
    [onDone],
  );

  return {
    state,
    approve: (entryId: string, note = "") => run("approve", entryId, note),
    sendBack: (entryId: string, note = "") => run("sendBack", entryId, note),
    reset: () => setState({ status: "idle" }),
  } as const;
}
