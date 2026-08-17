import { useState } from "react";

import { API, apiMessageFrom, type DictionaryResponse } from "../api";

const STATUS_LABELS: Record<DictionaryResponse["status"], string> = {
  draft: "Чернетка",
  configured: "Готовий до обробки",
};

/** BH-31 completion indicators: current status, missing gaps, and confirmation. */
export function DictionaryReadiness({
  dictionary,
  onConfigured,
}: {
  dictionary: DictionaryResponse;
  onConfigured: (dictionary: DictionaryResponse) => void;
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

  return (
    <div className="form-section" aria-labelledby="readiness-heading">
      <h2 id="readiness-heading">Готовність словника</h2>
      <p className={`status-badge status-badge--${dictionary.status}`} role="status">
        {STATUS_LABELS[dictionary.status]}
      </p>
      {blockers.length > 0 && (
        <ul className="readiness-blockers">
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
        <button
          type="button"
          disabled={!isReady || submitting}
          onClick={() => void handleConfigure()}
        >
          {submitting ? "Підтверджуємо…" : "Позначити як готовий до обробки"}
        </button>
      )}
    </div>
  );
}
