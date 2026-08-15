import { API_BASE_URL } from "../config";
import type { paths } from "./schema";

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
  },
} as const;

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
