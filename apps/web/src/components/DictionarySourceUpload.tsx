import { useEffect, useRef } from "react";

import type { DictionaryResponse } from "../api";
import {
  ALLOWED_UPLOAD_EXTENSION,
  MAX_CLIENT_UPLOAD_SIZE_BYTES,
  formatBytes,
  useDictionaryUpload,
} from "../hooks/useDictionaryUpload";

export function DictionarySourceUpload({
  onUploaded,
}: {
  onUploaded: (dictionary: DictionaryResponse) => void;
}) {
  const { state, selectFile, upload, retry, reset } = useDictionaryUpload();
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) selectFile(file);
  };

  const handleUpload = () => {
    if (state.status === "selected") void upload(state.file);
  };

  const handleChooseAnother = () => {
    reset();
    if (inputRef.current) inputRef.current.value = "";
  };

  useEffect(() => {
    if (state.status === "done") onUploaded(state.dictionary);
  }, [state, onUploaded]);

  if (state.status === "done") return null;

  return (
    <div className="form-section" aria-labelledby="upload-heading">
      <h2 id="upload-heading">1. Файл словника (PDF)</h2>
      <p className="section-hint">
        Оберіть оригінальний PDF. Максимальний розмір —{" "}
        {formatBytes(MAX_CLIENT_UPLOAD_SIZE_BYTES)}.
      </p>

      <div className="form-field">
        <label htmlFor="source-file">PDF-файл</label>
        <input
          ref={inputRef}
          id="source-file"
          type="file"
          accept={`${ALLOWED_UPLOAD_EXTENSION},application/pdf`}
          disabled={state.status === "uploading"}
          onChange={handleFileChange}
          aria-describedby="upload-status"
        />
      </div>

      <div aria-live="polite" id="upload-status">
        {(state.status === "selected" ||
          state.status === "uploading" ||
          state.status === "error" ||
          state.status === "duplicate") && (
          <p className="file-summary">
            {state.file.name} · {formatBytes(state.file.size)}
          </p>
        )}

        {state.status === "uploading" && (
          <div
            className="progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(state.progress * 100)}
            aria-label="Прогрес завантаження"
          >
            <div
              className="progress-bar"
              style={{ width: `${Math.round(state.progress * 100)}%` }}
            />
          </div>
        )}

        {state.status === "error" && (
          <p className="field-error" role="alert">
            {state.message}
          </p>
        )}

        {state.status === "duplicate" && (
          <p className="field-error" role="alert">
            Такий файл уже завантажено раніше
            {state.duplicate.title ? ` (« ${state.duplicate.title} »)` : ""}. Це не
            створило новий словник.
          </p>
        )}
      </div>

      <div className="form-actions">
        {state.status === "selected" && (
          <button type="button" onClick={handleUpload}>
            Завантажити файл
          </button>
        )}
        {state.status === "uploading" && (
          <button type="button" disabled>
            Завантажуємо…
          </button>
        )}
        {(state.status === "error" || state.status === "duplicate") && (
          <>
            <button type="button" onClick={retry}>
              Спробувати ще раз
            </button>
            <button type="button" className="secondary-button" onClick={handleChooseAnother}>
              Обрати інший файл
            </button>
          </>
        )}
      </div>
    </div>
  );
}
