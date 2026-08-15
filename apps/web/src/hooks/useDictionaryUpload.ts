import { useCallback, useRef, useState } from "react";

import {
  API,
  ApiError,
  apiMessageFrom,
  duplicateSourceFrom,
  fieldErrorsFrom,
  isAbortError,
  type DictionaryResponse,
  type DuplicateSourceResponse,
} from "../api";

/** Usability-only guard; the server enforces the authoritative limit. */
export const MAX_CLIENT_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024;
export const ALLOWED_UPLOAD_MIME_TYPE = "application/pdf";
export const ALLOWED_UPLOAD_EXTENSION = ".pdf";

export type UploadState =
  | { status: "idle" }
  | { status: "selected"; file: File }
  | { status: "uploading"; file: File; progress: number }
  | { status: "duplicate"; file: File; duplicate: DuplicateSourceResponse }
  | { status: "error"; file: File; message: string }
  | { status: "done"; file: File; dictionary: DictionaryResponse };

function clientValidationError(file: File): string | undefined {
  const name = file.name.toLowerCase();
  if (!name.endsWith(ALLOWED_UPLOAD_EXTENSION)) {
    return "Виберіть файл із розширенням .pdf.";
  }
  if (file.type && file.type !== ALLOWED_UPLOAD_MIME_TYPE) {
    return "Файл повинен мати тип application/pdf.";
  }
  if (file.size > MAX_CLIENT_UPLOAD_SIZE_BYTES) {
    return (
      "Файл перевищує дозволений розмір " +
      `${formatBytes(MAX_CLIENT_UPLOAD_SIZE_BYTES)}.`
    );
  }
  if (file.size === 0) {
    return "Порожній файл неможливо завантажити.";
  }
  return undefined;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  const units = ["КБ", "МБ", "ГБ"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unitIndex]}`;
}

/**
 * Drives BH-26's upload step: client pre-check, upload with progress, and
 * duplicate/error/success states. The server remains the source of truth for
 * every check performed here.
 */
export function useDictionaryUpload() {
  const [state, setState] = useState<UploadState>({ status: "idle" });
  const activeUpload = useRef<{ file: File; controller: AbortController } | null>(
    null,
  );

  const selectFile = useCallback((file: File) => {
    const validationError = clientValidationError(file);
    setState(
      validationError
        ? { status: "error", file, message: validationError }
        : { status: "selected", file },
    );
  }, []);

  const upload = useCallback(async (file: File) => {
    if (activeUpload.current) return;
    const controller = new AbortController();
    activeUpload.current = { file, controller };
    setState({ status: "uploading", file, progress: 0 });

    try {
      const dictionary = await API.dictionaries.upload(file, {
        signal: controller.signal,
        onProgress: (fraction) => {
          setState((previous) =>
            previous.status === "uploading"
              ? { ...previous, progress: fraction }
              : previous,
          );
        },
      });
      setState({ status: "done", file, dictionary });
    } catch (error) {
      if (isAbortError(error)) return;

      const duplicate = duplicateSourceFrom(error);
      if (duplicate) {
        setState({ status: "duplicate", file, duplicate });
        return;
      }
      const fieldErrors = fieldErrorsFrom(error);
      const message =
        fieldErrors?.file ??
        (error instanceof ApiError && error.status === 413
          ? apiMessageFrom(error)
          : undefined) ??
        apiMessageFrom(error) ??
        "Не вдалося завантажити файл. Спробуйте ще раз.";
      setState({ status: "error", file, message });
    } finally {
      activeUpload.current = null;
    }
  }, []);

  const retry = useCallback(() => {
    if (state.status === "error" || state.status === "duplicate") {
      setState({ status: "selected", file: state.file });
    }
  }, [state]);

  const reset = useCallback(() => {
    activeUpload.current?.controller.abort();
    setState({ status: "idle" });
  }, []);

  return { state, selectFile, upload, retry, reset } as const;
}
