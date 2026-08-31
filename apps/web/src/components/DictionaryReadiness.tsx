import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { API, apiMessageFrom, type DictionaryResponse } from "../api";
import {
  DICTIONARY_STATUS_BADGE_VARIANT,
  DICTIONARY_STATUS_LABELS,
} from "../dictionaryStatusLabels";

/** BH-31/BH-58 completion indicators: current status, blockers, and confirmation. */
export function DictionaryReadiness({
  dictionary,
  onConfigured,
  onScanned,
}: {
  dictionary: DictionaryResponse;
  onConfigured: (dictionary: DictionaryResponse) => void;
  onScanned: (dictionary: DictionaryResponse) => void;
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

  return (
    <div className="form-section" aria-labelledby="readiness-heading">
      <h2 id="readiness-heading">Готовність словника</h2>
      <Badge
        size="lg"
        variant={DICTIONARY_STATUS_BADGE_VARIANT[dictionary.status]}
        role="status"
      >
        {DICTIONARY_STATUS_LABELS[dictionary.status]}
      </Badge>
      {blockers.length > 0 && (
        <ul className="mt-2 mb-0 list-disc pl-5 text-[0.92rem]">
          {blockers.map((blocker) => (
            <li key={blocker.code}>{blocker.message}</li>
          ))}
        </ul>
      )}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {dictionary.status === "draft" && (
        <Button
          type="button"
          disabled={!isReady || submitting}
          onClick={() => void handleConfigure()}
        >
          {submitting ? "Підтверджуємо…" : "Позначити як готовий до обробки"}
        </Button>
      )}
      {dictionary.status === "configured" && (
        <Button
          type="button"
          disabled={submitting}
          onClick={() => void handleFinishScanning()}
        >
          {submitting ? "Завершуємо…" : "Завершити сканування"}
        </Button>
      )}
    </div>
  );
}
