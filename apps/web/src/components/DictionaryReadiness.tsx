import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { API, apiMessageFrom, type DictionaryResponse } from "../api";
import {
  DICTIONARY_STATUS_BADGE_VARIANT,
  DICTIONARY_STATUS_LABELS,
} from "../dictionaryStatusLabels";

/** Current status, readiness blockers, and the one action available next:
 * configure a draft, finish scanning, or publish a fully processed dictionary.
 * ``in_progress`` / ``processed`` are reached automatically, so they offer no
 * button except the final publish. */
export function DictionaryReadiness({
  dictionary,
  onConfigured,
  onScanned,
  onPublished,
}: {
  dictionary: DictionaryResponse;
  onConfigured: (dictionary: DictionaryResponse) => void;
  onScanned: (dictionary: DictionaryResponse) => void;
  onPublished?: (dictionary: DictionaryResponse) => void;
}) {
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const blockers = dictionary.readiness_blockers;
  const isReady = blockers.length === 0;

  const handleConfigure = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const updated = await API.dictionaries.configure(dictionary.id);
      onConfigured(updated);
    } catch (submitError) {
      setError(
        apiMessageFrom(submitError) ??
          "Не вдалося підтвердити готовність. Спробуйте ще раз.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleFinishScanning = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await API.dictionaries.finishScanning(dictionary.id);
      onScanned({ ...dictionary, status: result.status });
    } catch (submitError) {
      setError(
        apiMessageFrom(submitError) ??
          "Не вдалося завершити сканування. Спробуйте ще раз.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handlePublish = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const result = await API.dictionaries.publish(dictionary.id);
      (onPublished ?? onScanned)({ ...dictionary, status: result.status });
    } catch (submitError) {
      setError(
        apiMessageFrom(submitError) ??
          "Не вдалося опублікувати словник. Спробуйте ще раз.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      className="flex flex-col items-start gap-1.5 sm:items-end"
      aria-labelledby="readiness-heading"
    >
      <div className="flex items-center gap-2">
        <span
          id="readiness-heading"
          className="text-[0.7rem] font-[750] tracking-[0.12em] text-muted-foreground uppercase"
        >
          Статус словника
        </span>
        <Badge
          size="lg"
          variant={DICTIONARY_STATUS_BADGE_VARIANT[dictionary.status]}
          role="status"
        >
          {DICTIONARY_STATUS_LABELS[dictionary.status]}
        </Badge>
      </div>
      {dictionary.status === "draft" && (
        <Button
          type="button"
          size="sm"
          disabled={!isReady || submitting}
          onClick={() => void handleConfigure()}
        >
          {submitting ? "Підтверджуємо…" : "Позначити як готовий до обробки"}
        </Button>
      )}
      {dictionary.status === "configured" && (
        <Button
          type="button"
          size="sm"
          disabled={submitting}
          onClick={() => void handleFinishScanning()}
        >
          {submitting ? "Завершуємо…" : "Завершити сканування"}
        </Button>
      )}
      {dictionary.status === "processed" && (
        <Button
          type="button"
          size="sm"
          disabled={submitting}
          onClick={() => void handlePublish()}
        >
          {submitting ? "Публікуємо…" : "Опублікувати словник"}
        </Button>
      )}
      {blockers.length > 0 && (
        <ul className="m-0 max-w-[24rem] list-disc pl-5 text-left text-[0.8rem] text-warning-foreground">
          {blockers.map((blocker) => (
            <li key={blocker.code}>{blocker.message}</li>
          ))}
        </ul>
      )}
      {error && (
        <p
          className="m-0 max-w-[24rem] text-[0.82rem] text-destructive"
          role="alert"
        >
          {error}
        </p>
      )}
    </div>
  );
}
