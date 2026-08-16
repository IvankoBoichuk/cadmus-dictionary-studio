import { API_BASE_URL } from "../config";
import type { components, paths } from "./schema";

type RegistrationOperation = paths["/auth/register"]["post"];
type RegistrationRequest =
  RegistrationOperation["requestBody"]["content"]["application/json"];
type RegistrationResponse =
  RegistrationOperation["responses"][201]["content"]["application/json"];
type FieldErrorsResponse =
  RegistrationOperation["responses"][422]["content"]["application/json"];
type VerificationOperation = paths["/auth/verify-email"]["post"];
type VerificationRequest =
  VerificationOperation["requestBody"]["content"]["application/json"];
type VerificationResponse =
  VerificationOperation["responses"][200]["content"]["application/json"];
type VerificationErrorResponse =
  VerificationOperation["responses"][400]["content"]["application/json"];
type ValidationErrorResponse =
  VerificationOperation["responses"][422]["content"]["application/json"];
type LoginOperation = paths["/auth/login"]["post"];
type LoginRequest =
  LoginOperation["requestBody"]["content"]["application/json"];
export type AuthenticatedUser =
  LoginOperation["responses"][200]["content"]["application/json"];
type AuthenticationErrorResponse =
  LoginOperation["responses"][401]["content"]["application/json"];
type SessionOperation = paths["/auth/session"]["get"];
type SessionResponse =
  SessionOperation["responses"][200]["content"]["application/json"];
type LogoutOperation = paths["/auth/logout"]["post"];
type LogoutResponse =
  LogoutOperation["responses"][200]["content"]["application/json"];
type ForgotPasswordOperation = paths["/auth/forgot-password"]["post"];
type ForgotPasswordRequest =
  ForgotPasswordOperation["requestBody"]["content"]["application/json"];
type ForgotPasswordResponse =
  ForgotPasswordOperation["responses"][200]["content"]["application/json"];
type ResetPasswordOperation = paths["/auth/reset-password"]["post"];
type ResetPasswordRequest =
  ResetPasswordOperation["requestBody"]["content"]["application/json"];
type ResetPasswordResponse =
  ResetPasswordOperation["responses"][200]["content"]["application/json"];
type PasswordResetErrorResponse =
  ResetPasswordOperation["responses"][400]["content"]["application/json"];

export type LegalStatus = components["schemas"]["LegalStatus"];
export type ContributorRole = components["schemas"]["ContributorRole"];
export type InspectionStatus = components["schemas"]["InspectionStatus"];
export type DictionaryStatus = components["schemas"]["DictionaryStatus"];
export type ContributorRequest = components["schemas"]["ContributorRequest"];

type UploadDictionaryOperation = paths["/dictionaries/upload"]["post"];
export type DictionaryResponse =
  UploadDictionaryOperation["responses"][202]["content"]["application/json"];
export type DuplicateSourceResponse =
  UploadDictionaryOperation["responses"][409]["content"]["application/json"];
type UploadTooLargeResponse =
  UploadDictionaryOperation["responses"][413]["content"]["application/json"];
type UploadFieldErrorsResponse =
  UploadDictionaryOperation["responses"][422]["content"]["application/json"];

type GetDictionaryOperation = paths["/dictionaries/{dictionary_id}"]["get"];
type DictionaryNotFoundResponse =
  GetDictionaryOperation["responses"][404]["content"]["application/json"];

type ListDictionariesOperation = paths["/dictionaries"]["get"];
export type DictionaryListResponse =
  ListDictionariesOperation["responses"][200]["content"]["application/json"];

type DeleteDictionaryOperation = paths["/dictionaries/{dictionary_id}"]["delete"];
type DeleteDictionaryNotFoundResponse =
  DeleteDictionaryOperation["responses"][404]["content"]["application/json"];

type SaveMetadataOperation = paths["/dictionaries/{dictionary_id}"]["patch"];
export type SaveMetadataRequest =
  SaveMetadataOperation["requestBody"]["content"]["application/json"];
type SaveMetadataFieldErrorsResponse =
  SaveMetadataOperation["responses"][422]["content"]["application/json"];

export type AbbreviationCategory = components["schemas"]["AbbreviationCategory"];
export type AbbreviationRequest = components["schemas"]["AbbreviationRequest"];
export type AbbreviationResponse = components["schemas"]["AbbreviationResponse"];
export type ImportRowResponse = components["schemas"]["ImportRowResponse"];
export type ImportPreviewResponse = components["schemas"]["ImportPreviewResponse"];
export type ImportCommitResponse = components["schemas"]["ImportCommitResponse"];
export type DuplicateAbbreviationResponse =
  components["schemas"]["DuplicateAbbreviationResponse"];

type ListAbbreviationsOperation =
  paths["/dictionaries/{dictionary_id}/abbreviations"]["get"];
type AbbreviationsNotFoundResponse =
  ListAbbreviationsOperation["responses"][404]["content"]["application/json"];

type CreateAbbreviationOperation =
  paths["/dictionaries/{dictionary_id}/abbreviations"]["post"];
type AbbreviationFieldErrorsResponse =
  CreateAbbreviationOperation["responses"][422]["content"]["application/json"];

type ImportPreviewOperation =
  paths["/dictionaries/{dictionary_id}/abbreviations/import/preview"]["post"];
type UnparsableImportResponse =
  ImportPreviewOperation["responses"][422]["content"]["application/json"];

type ImportCommitOperation =
  paths["/dictionaries/{dictionary_id}/abbreviations/import/commit"]["post"];
export type ImportCommitRequest =
  ImportCommitOperation["requestBody"]["content"]["application/json"];

export type ApiErrorKind = "http" | "network" | "invalid-response";

export class ApiError<Failure = unknown> extends Error {
  constructor(
    readonly kind: ApiErrorKind,
    readonly status?: number,
    readonly payload?: Failure,
    options?: ErrorOptions,
  ) {
    super(`API request failed: ${kind}`, options);
    this.name = "ApiError";
  }
}

type RequestOptions = {
  signal?: AbortSignal;
};

async function request<Success, Failure>(
  path: keyof paths,
  init: RequestInit,
): Promise<Success> {
  let response: Response | undefined;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      credentials: "same-origin",
      ...init,
    });
    const payload = (await response.json()) as Success | Failure;

    if (!response.ok) {
      throw new ApiError<Failure>("http", response.status, payload as Failure);
    }
    return payload as Success;
  } catch (error) {
    if (error instanceof ApiError || isAbortError(error)) throw error;
    throw new ApiError(
      response ? "invalid-response" : "network",
      response?.status,
      undefined,
      { cause: error },
    );
  }
}

function post<Body, Success, Failure>(
  path: keyof paths,
  body: Body,
  options: RequestOptions = {},
): Promise<Success> {
  return request<Success, Failure>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: options.signal,
  });
}

function get<Success, Failure>(
  path: keyof paths,
  options: RequestOptions = {},
): Promise<Success> {
  return request<Success, Failure>(path, {
    method: "GET",
    signal: options.signal,
  });
}

function postWithoutBody<Success, Failure>(
  path: keyof paths,
  options: RequestOptions = {},
): Promise<Success> {
  return request<Success, Failure>(path, {
    method: "POST",
    signal: options.signal,
  });
}

function patch<Body, Success, Failure>(
  path: keyof paths,
  body: Body,
  options: RequestOptions = {},
): Promise<Success> {
  return request<Success, Failure>(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: options.signal,
  });
}

/** A 204 No Content response has no body, so this never calls `response.json()`. */
async function del<Failure>(
  path: keyof paths,
  options: RequestOptions = {},
): Promise<void> {
  let response: Response | undefined;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: "DELETE",
      credentials: "same-origin",
      signal: options.signal,
    });
    if (!response.ok) {
      let payload: Failure | undefined;
      try {
        payload = (await response.json()) as Failure;
      } catch {
        payload = undefined;
      }
      throw new ApiError<Failure>("http", response.status, payload);
    }
  } catch (error) {
    if (error instanceof ApiError || isAbortError(error)) throw error;
    throw new ApiError(
      response ? "invalid-response" : "network",
      response?.status,
      undefined,
      { cause: error },
    );
  }
}

/** A dynamic resource path is still a real endpoint template; only the ID varies. */
function dictionaryPath(dictionaryId: string): keyof paths {
  return `/dictionaries/${dictionaryId}` as keyof paths;
}

function abbreviationsPath(dictionaryId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/abbreviations` as keyof paths;
}

function abbreviationPath(dictionaryId: string, abbreviationId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/abbreviations/${abbreviationId}` as keyof paths;
}

function abbreviationsImportPreviewPath(dictionaryId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/abbreviations/import/preview` as keyof paths;
}

function abbreviationsImportCommitPath(dictionaryId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/abbreviations/import/commit` as keyof paths;
}

type UploadOptions = RequestOptions & {
  onProgress?: (fraction: number) => void;
};

function uploadFile<Success, Failure>(
  path: keyof paths,
  file: File,
  options: UploadOptions = {},
): Promise<Success> {
  return new Promise<Success>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}${path}`, true);
    xhr.responseType = "text";

    if (options.signal) {
      if (options.signal.aborted) {
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }
      options.signal.addEventListener("abort", () => xhr.abort());
    }

    xhr.upload.onprogress = (event) => {
      if (options.onProgress && event.lengthComputable) {
        options.onProgress(event.loaded / event.total);
      }
    };
    xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));
    xhr.onerror = () => reject(new ApiError<Failure>("network"));
    xhr.onload = () => {
      let payload: unknown;
      try {
        payload = xhr.responseText ? JSON.parse(xhr.responseText) : undefined;
      } catch (error) {
        reject(
          new ApiError<Failure>("invalid-response", xhr.status, undefined, {
            cause: error,
          }),
        );
        return;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload as Success);
      } else {
        reject(new ApiError<Failure>("http", xhr.status, payload as Failure));
      }
    };

    const formData = new FormData();
    formData.append("file", file);
    xhr.send(formData);
  });
}

const verificationRequests = new Map<string, Promise<VerificationResponse>>();
let currentSessionRequest: Promise<SessionResponse> | undefined;

export const API = {
  auth: {
    login(
      request: LoginRequest,
      options?: RequestOptions,
    ): Promise<AuthenticatedUser> {
      return post<
        LoginRequest,
        AuthenticatedUser,
        AuthenticationErrorResponse | ValidationErrorResponse
      >("/auth/login", request, options);
    },

    currentSession(options?: RequestOptions): Promise<SessionResponse> {
      if (currentSessionRequest) return currentSessionRequest;
      currentSessionRequest = get<SessionResponse, AuthenticationErrorResponse>(
        "/auth/session",
        options,
      );
      void currentSessionRequest.then(
        () => {
          currentSessionRequest = undefined;
        },
        () => {
          currentSessionRequest = undefined;
        },
      );
      return currentSessionRequest;
    },

    logout(options?: RequestOptions): Promise<LogoutResponse> {
      return postWithoutBody<LogoutResponse, never>("/auth/logout", options);
    },

    register(
      request: RegistrationRequest,
      options?: RequestOptions,
    ): Promise<RegistrationResponse> {
      return post<
        RegistrationRequest,
        RegistrationResponse,
        FieldErrorsResponse | ValidationErrorResponse
      >("/auth/register", request, options);
    },

    verifyEmail(
      request: VerificationRequest,
    ): Promise<VerificationResponse> {
      const existingRequest = verificationRequests.get(request.token);
      if (existingRequest) return existingRequest;

      const verificationRequest = post<
        VerificationRequest,
        VerificationResponse,
        VerificationErrorResponse | ValidationErrorResponse
      >("/auth/verify-email", request);
      verificationRequests.set(request.token, verificationRequest);
      void verificationRequest.then(
        () => verificationRequests.delete(request.token),
        () => verificationRequests.delete(request.token),
      );
      return verificationRequest;
    },

    forgotPassword(
      request: ForgotPasswordRequest,
      options?: RequestOptions,
    ): Promise<ForgotPasswordResponse> {
      return post<ForgotPasswordRequest, ForgotPasswordResponse, ValidationErrorResponse>(
        "/auth/forgot-password",
        request,
        options,
      );
    },

    resetPassword(
      request: ResetPasswordRequest,
      options?: RequestOptions,
    ): Promise<ResetPasswordResponse> {
      return post<
        ResetPasswordRequest,
        ResetPasswordResponse,
        PasswordResetErrorResponse | FieldErrorsResponse | ValidationErrorResponse
      >("/auth/reset-password", request, options);
    },
  },

  dictionaries: {
    upload(
      file: File,
      options?: UploadOptions,
    ): Promise<DictionaryResponse> {
      return uploadFile<
        DictionaryResponse,
        | UploadFieldErrorsResponse
        | DuplicateSourceResponse
        | UploadTooLargeResponse
        | ValidationErrorResponse
      >("/dictionaries/upload", file, options);
    },

    get(
      dictionaryId: string,
      options?: RequestOptions,
    ): Promise<DictionaryResponse> {
      return get<DictionaryResponse, DictionaryNotFoundResponse>(
        dictionaryPath(dictionaryId),
        options,
      );
    },

    list(options?: RequestOptions): Promise<DictionaryListResponse> {
      return get<DictionaryListResponse, never>("/dictionaries", options);
    },

    delete(dictionaryId: string, options?: RequestOptions): Promise<void> {
      return del<DeleteDictionaryNotFoundResponse>(
        dictionaryPath(dictionaryId),
        options,
      );
    },

    saveMetadata(
      dictionaryId: string,
      body: SaveMetadataRequest,
      options?: RequestOptions,
    ): Promise<DictionaryResponse> {
      return patch<
        SaveMetadataRequest,
        DictionaryResponse,
        SaveMetadataFieldErrorsResponse | DictionaryNotFoundResponse
      >(dictionaryPath(dictionaryId), body, options);
    },
  },

  abbreviations: {
    list(
      dictionaryId: string,
      options?: RequestOptions,
    ): Promise<AbbreviationResponse[]> {
      return get<AbbreviationResponse[], AbbreviationsNotFoundResponse>(
        abbreviationsPath(dictionaryId),
        options,
      );
    },

    create(
      dictionaryId: string,
      body: AbbreviationRequest,
      options?: RequestOptions,
    ): Promise<AbbreviationResponse> {
      return post<
        AbbreviationRequest,
        AbbreviationResponse,
        | AbbreviationFieldErrorsResponse
        | DuplicateAbbreviationResponse
        | AbbreviationsNotFoundResponse
      >(abbreviationsPath(dictionaryId), body, options);
    },

    update(
      dictionaryId: string,
      abbreviationId: string,
      body: AbbreviationRequest,
      options?: RequestOptions,
    ): Promise<AbbreviationResponse> {
      return patch<
        AbbreviationRequest,
        AbbreviationResponse,
        | AbbreviationFieldErrorsResponse
        | DuplicateAbbreviationResponse
        | AbbreviationsNotFoundResponse
      >(abbreviationPath(dictionaryId, abbreviationId), body, options);
    },

    delete(
      dictionaryId: string,
      abbreviationId: string,
      options?: RequestOptions,
    ): Promise<void> {
      return del<AbbreviationsNotFoundResponse>(
        abbreviationPath(dictionaryId, abbreviationId),
        options,
      );
    },

    importPreview(
      dictionaryId: string,
      file: File,
      options?: UploadOptions,
    ): Promise<ImportPreviewResponse> {
      return uploadFile<ImportPreviewResponse, UnparsableImportResponse>(
        abbreviationsImportPreviewPath(dictionaryId),
        file,
        options,
      );
    },

    importCommit(
      dictionaryId: string,
      body: ImportCommitRequest,
      options?: RequestOptions,
    ): Promise<ImportCommitResponse> {
      return post<ImportCommitRequest, ImportCommitResponse, AbbreviationsNotFoundResponse>(
        abbreviationsImportCommitPath(dictionaryId),
        body,
        options,
      );
    },
  },
} as const;

export function abbreviationsExportUrl(
  dictionaryId: string,
  format: "json" | "csv",
): string {
  return `${API_BASE_URL}/dictionaries/${dictionaryId}/abbreviations/export?format=${format}`;
}

export function dictionaryThumbnailUrl(dictionaryId: string): string {
  return `${API_BASE_URL}/dictionaries/${dictionaryId}/thumbnail`;
}

export function fieldErrorsFrom(error: unknown): FieldErrorsResponse["errors"] | undefined {
  if (!(error instanceof ApiError) || error.kind !== "http") return undefined;
  const payload = error.payload as FieldErrorsResponse | ValidationErrorResponse;
  return typeof payload === "object" && payload !== null && "errors" in payload
    ? payload.errors
    : undefined;
}

export function apiMessageFrom(error: unknown): string | undefined {
  if (!(error instanceof ApiError) || error.kind !== "http") return undefined;
  const payload = error.payload;
  if (typeof payload !== "object" || payload === null || !("message" in payload)) {
    return undefined;
  }
  return typeof payload.message === "string" ? payload.message : undefined;
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function duplicateSourceFrom(
  error: unknown,
): DuplicateSourceResponse | undefined {
  if (!(error instanceof ApiError) || error.kind !== "http" || error.status !== 409) {
    return undefined;
  }
  const payload = error.payload as DuplicateSourceResponse | undefined;
  return payload && typeof payload === "object" && "dictionary_id" in payload
    ? payload
    : undefined;
}

export function duplicateAbbreviationFrom(
  error: unknown,
): DuplicateAbbreviationResponse | undefined {
  if (!(error instanceof ApiError) || error.kind !== "http" || error.status !== 409) {
    return undefined;
  }
  const payload = error.payload as DuplicateAbbreviationResponse | undefined;
  return payload && typeof payload === "object" && "abbreviation_id" in payload
    ? payload
    : undefined;
}
