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

export type ApiResult<Success, Failure> =
  | { ok: true; data: Success }
  | { ok: false; error: Failure; status: number };

async function post<Body, Success, Failure>(
  path: keyof paths,
  body: Body,
): Promise<ApiResult<Success, Failure>> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = (await response.json()) as Success | Failure;
  return response.ok
    ? { ok: true, data: payload as Success }
    : { ok: false, error: payload as Failure, status: response.status };
}

export const API = {
  auth: {
    register(
      request: RegistrationRequest,
    ): Promise<
      ApiResult<RegistrationResponse, FieldErrorsResponse | ValidationErrorResponse>
    > {
      return post("/auth/register", request);
    },

    verifyEmail(
      request: VerificationRequest,
    ): Promise<
      ApiResult<
        VerificationResponse,
        VerificationErrorResponse | ValidationErrorResponse
      >
    > {
      return post("/auth/verify-email", request);
    },
  },
} as const;

export function fieldErrorsFrom(
  response: FieldErrorsResponse | ValidationErrorResponse,
): FieldErrorsResponse["errors"] | undefined {
  return "errors" in response ? response.errors : undefined;
}
