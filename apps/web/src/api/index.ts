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

export type ReadinessBlocker = components["schemas"]["ReadinessBlockerResponse"];

type ConfigureDictionaryOperation =
  paths["/dictionaries/{dictionary_id}/configure"]["post"];
export type ConfigureDictionaryNotReadyResponse =
  ConfigureDictionaryOperation["responses"][422]["content"]["application/json"];
type ConfigureDictionaryNotFoundResponse =
  ConfigureDictionaryOperation["responses"][404]["content"]["application/json"];

export type AbbreviationCategory = components["schemas"]["AbbreviationCategory"];
export type AbbreviationRequest = components["schemas"]["AbbreviationRequest"];
export type AbbreviationResponse = components["schemas"]["AbbreviationResponse"];
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

// The `Import*Response`/`Import*Request` schema names collide across the
// abbreviations and settlements routers, so FastAPI disambiguates their
// OpenAPI component names with a module-path prefix. Deriving these types
// from the operation itself (rather than a `components["schemas"][...]`
// literal) keeps this file oblivious to whatever prefix FastAPI picks.
type ImportPreviewOperation =
  paths["/dictionaries/{dictionary_id}/abbreviations/import/preview"]["post"];
export type ImportPreviewResponse =
  ImportPreviewOperation["responses"][200]["content"]["application/json"];
export type ImportRowResponse = ImportPreviewResponse["rows"][number];
type UnparsableImportResponse =
  ImportPreviewOperation["responses"][422]["content"]["application/json"];

type ImportCommitOperation =
  paths["/dictionaries/{dictionary_id}/abbreviations/import/commit"]["post"];
export type ImportCommitRequest =
  ImportCommitOperation["requestBody"]["content"]["application/json"];
export type ImportCommitResponse =
  ImportCommitOperation["responses"][200]["content"]["application/json"];

export type AreaResponse = components["schemas"]["AreaResponse"];
export type RegionResponse = components["schemas"]["RegionResponse"];
export type CommunityResponse = components["schemas"]["CommunityResponse"];
export type CommunityGeometryResponse =
  components["schemas"]["CommunityGeometryResponse"];

type GetCommunityOperation =
  paths["/geography/communities/{community_id}"]["get"];
type CommunityNotFoundResponse =
  GetCommunityOperation["responses"][404]["content"]["application/json"];
type GetCommunityGeoJsonOperation =
  paths["/geography/communities/{community_id}/geo_json"]["get"];
type CommunityGeoJsonNotFoundResponse =
  GetCommunityGeoJsonOperation["responses"][404]["content"]["application/json"];

export type SettlementMappingStatus =
  components["schemas"]["SettlementMappingStatus"];
export type SettlementMappingRequest =
  components["schemas"]["SettlementMappingRequest"];
export type SettlementMappingResponse =
  components["schemas"]["SettlementMappingResponse"];
export type SettlementSuggestionResponse =
  components["schemas"]["SettlementSuggestionResponse"];
export type DuplicateSettlementMappingResponse =
  components["schemas"]["DuplicateSettlementMappingResponse"];

type ListSettlementMappingsOperation =
  paths["/dictionaries/{dictionary_id}/settlements"]["get"];
type SettlementMappingsNotFoundResponse =
  ListSettlementMappingsOperation["responses"][404]["content"]["application/json"];

type CreateSettlementMappingOperation =
  paths["/dictionaries/{dictionary_id}/settlements"]["post"];
type SettlementMappingFieldErrorsResponse =
  CreateSettlementMappingOperation["responses"][422]["content"]["application/json"];

type ConfirmSettlementMappingOperation =
  paths["/dictionaries/{dictionary_id}/settlements/{mapping_id}/confirm"]["post"];
type ConfirmSettlementMappingErrorResponse =
  ConfirmSettlementMappingOperation["responses"][422]["content"]["application/json"];

type SettlementImportPreviewOperation =
  paths["/dictionaries/{dictionary_id}/settlements/import/preview"]["post"];
export type SettlementImportPreviewResponse =
  SettlementImportPreviewOperation["responses"][200]["content"]["application/json"];
export type SettlementImportRowResponse =
  SettlementImportPreviewResponse["rows"][number];
type UnparsableSettlementImportResponse =
  SettlementImportPreviewOperation["responses"][422]["content"]["application/json"];

type SettlementImportCommitOperation =
  paths["/dictionaries/{dictionary_id}/settlements/import/commit"]["post"];
export type SettlementImportCommitRequest =
  SettlementImportCommitOperation["requestBody"]["content"]["application/json"];
export type SettlementImportCommitResponse =
  SettlementImportCommitOperation["responses"][200]["content"]["application/json"];

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

function dictionaryConfigurePath(dictionaryId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/configure` as keyof paths;
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

function geographyRegionsPath(areaId?: string): keyof paths {
  const query = areaId ? `?area_id=${encodeURIComponent(areaId)}` : "";
  return `/geography/regions${query}` as keyof paths;
}

function geographyCommunitiesPath(areaId?: string, regionId?: string): keyof paths {
  const params = new URLSearchParams();
  if (areaId) params.set("area_id", areaId);
  if (regionId) params.set("region_id", regionId);
  const query = params.toString();
  return `/geography/communities${query ? `?${query}` : ""}` as keyof paths;
}

function geographyCommunityPath(communityId: string): keyof paths {
  return `/geography/communities/${communityId}` as keyof paths;
}

function geographyCommunityGeoJsonPath(communityId: string): keyof paths {
  return `/geography/communities/${communityId}/geo_json` as keyof paths;
}

function settlementsPath(dictionaryId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/settlements` as keyof paths;
}

function settlementPath(dictionaryId: string, mappingId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/settlements/${mappingId}` as keyof paths;
}

function settlementConfirmPath(dictionaryId: string, mappingId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/settlements/${mappingId}/confirm` as keyof paths;
}

function settlementUnconfirmPath(dictionaryId: string, mappingId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/settlements/${mappingId}/unconfirm` as keyof paths;
}

export type SettlementSearchFilters = {
  query?: string;
  areaId?: string;
  regionId?: string;
  communityId?: string;
  category?: string;
};

function settlementsSearchPath(
  dictionaryId: string,
  filters: SettlementSearchFilters,
): keyof paths {
  const params = new URLSearchParams();
  if (filters.query) params.set("query", filters.query);
  if (filters.areaId) params.set("area_id", filters.areaId);
  if (filters.regionId) params.set("region_id", filters.regionId);
  if (filters.communityId) params.set("community_id", filters.communityId);
  if (filters.category) params.set("category", filters.category);
  const query = params.toString();
  return `/dictionaries/${dictionaryId}/settlements/search${
    query ? `?${query}` : ""
  }` as keyof paths;
}

function settlementsImportPreviewPath(dictionaryId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/settlements/import/preview` as keyof paths;
}

function settlementsImportCommitPath(dictionaryId: string): keyof paths {
  return `/dictionaries/${dictionaryId}/settlements/import/commit` as keyof paths;
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

    configure(
      dictionaryId: string,
      options?: RequestOptions,
    ): Promise<DictionaryResponse> {
      return postWithoutBody<
        DictionaryResponse,
        ConfigureDictionaryNotReadyResponse | ConfigureDictionaryNotFoundResponse
      >(dictionaryConfigurePath(dictionaryId), options);
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

  geography: {
    listAreas(options?: RequestOptions): Promise<AreaResponse[]> {
      return get<AreaResponse[], never>("/geography/areas", options);
    },

    listRegions(areaId?: string, options?: RequestOptions): Promise<RegionResponse[]> {
      return get<RegionResponse[], never>(geographyRegionsPath(areaId), options);
    },

    listCommunities(
      filters: { areaId?: string; regionId?: string } = {},
      options?: RequestOptions,
    ): Promise<CommunityResponse[]> {
      return get<CommunityResponse[], never>(
        geographyCommunitiesPath(filters.areaId, filters.regionId),
        options,
      );
    },

    getCommunity(
      communityId: string,
      options?: RequestOptions,
    ): Promise<CommunityResponse> {
      return get<CommunityResponse, CommunityNotFoundResponse>(
        geographyCommunityPath(communityId),
        options,
      );
    },

    getCommunityGeoJson(
      communityId: string,
      options?: RequestOptions,
    ): Promise<CommunityGeometryResponse> {
      return get<CommunityGeometryResponse, CommunityGeoJsonNotFoundResponse>(
        geographyCommunityGeoJsonPath(communityId),
        options,
      );
    },
  },

  settlements: {
    list(
      dictionaryId: string,
      options?: RequestOptions,
    ): Promise<SettlementMappingResponse[]> {
      return get<SettlementMappingResponse[], SettlementMappingsNotFoundResponse>(
        settlementsPath(dictionaryId),
        options,
      );
    },

    create(
      dictionaryId: string,
      body: SettlementMappingRequest,
      options?: RequestOptions,
    ): Promise<SettlementMappingResponse> {
      return post<
        SettlementMappingRequest,
        SettlementMappingResponse,
        | SettlementMappingFieldErrorsResponse
        | DuplicateSettlementMappingResponse
        | SettlementMappingsNotFoundResponse
      >(settlementsPath(dictionaryId), body, options);
    },

    update(
      dictionaryId: string,
      mappingId: string,
      body: SettlementMappingRequest,
      options?: RequestOptions,
    ): Promise<SettlementMappingResponse> {
      return patch<
        SettlementMappingRequest,
        SettlementMappingResponse,
        | SettlementMappingFieldErrorsResponse
        | DuplicateSettlementMappingResponse
        | SettlementMappingsNotFoundResponse
      >(settlementPath(dictionaryId, mappingId), body, options);
    },

    delete(
      dictionaryId: string,
      mappingId: string,
      options?: RequestOptions,
    ): Promise<void> {
      return del<SettlementMappingsNotFoundResponse>(
        settlementPath(dictionaryId, mappingId),
        options,
      );
    },

    confirm(
      dictionaryId: string,
      mappingId: string,
      options?: RequestOptions,
    ): Promise<SettlementMappingResponse> {
      return postWithoutBody<
        SettlementMappingResponse,
        ConfirmSettlementMappingErrorResponse | SettlementMappingsNotFoundResponse
      >(settlementConfirmPath(dictionaryId, mappingId), options);
    },

    unconfirm(
      dictionaryId: string,
      mappingId: string,
      options?: RequestOptions,
    ): Promise<SettlementMappingResponse> {
      return postWithoutBody<
        SettlementMappingResponse,
        SettlementMappingsNotFoundResponse
      >(settlementUnconfirmPath(dictionaryId, mappingId), options);
    },

    search(
      dictionaryId: string,
      filters: SettlementSearchFilters = {},
      options?: RequestOptions,
    ): Promise<SettlementSuggestionResponse[]> {
      return get<SettlementSuggestionResponse[], SettlementMappingsNotFoundResponse>(
        settlementsSearchPath(dictionaryId, filters),
        options,
      );
    },

    importPreview(
      dictionaryId: string,
      file: File,
      options?: UploadOptions,
    ): Promise<SettlementImportPreviewResponse> {
      return uploadFile<
        SettlementImportPreviewResponse,
        UnparsableSettlementImportResponse
      >(settlementsImportPreviewPath(dictionaryId), file, options);
    },

    importCommit(
      dictionaryId: string,
      body: SettlementImportCommitRequest,
      options?: RequestOptions,
    ): Promise<SettlementImportCommitResponse> {
      return post<
        SettlementImportCommitRequest,
        SettlementImportCommitResponse,
        SettlementMappingsNotFoundResponse
      >(settlementsImportCommitPath(dictionaryId), body, options);
    },
  },
} as const;

export function abbreviationsExportUrl(
  dictionaryId: string,
  format: "json" | "csv",
): string {
  return `${API_BASE_URL}/dictionaries/${dictionaryId}/abbreviations/export?format=${format}`;
}

export function settlementsExportUrl(
  dictionaryId: string,
  format: "json" | "csv",
): string {
  return `${API_BASE_URL}/dictionaries/${dictionaryId}/settlements/export?format=${format}`;
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

export function duplicateSettlementMappingFrom(
  error: unknown,
): DuplicateSettlementMappingResponse | undefined {
  if (!(error instanceof ApiError) || error.kind !== "http" || error.status !== 409) {
    return undefined;
  }
  const payload = error.payload as DuplicateSettlementMappingResponse | undefined;
  return payload && typeof payload === "object" && "mapping_id" in payload
    ? payload
    : undefined;
}

export function readinessBlockersFrom(error: unknown): ReadinessBlocker[] | undefined {
  if (!(error instanceof ApiError) || error.kind !== "http" || error.status !== 422) {
    return undefined;
  }
  const payload = error.payload as ConfigureDictionaryNotReadyResponse | undefined;
  return payload && typeof payload === "object" && "blockers" in payload
    ? payload.blockers
    : undefined;
}
