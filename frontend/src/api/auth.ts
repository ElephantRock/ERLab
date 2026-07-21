/** Auth API client (BATCH-28). */

import { apiFetchUnchecked } from "./client";

// ── Types ──────────────────────────────────────────────────────────

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  role: "admin" | "user";
}

export interface AuthResponse {
  token: string;
  user: AuthUser;
}

// ── API Functions ──────────────────────────────────────────────────

export async function register(
  username: string,
  email: string,
  password: string,
): Promise<AuthResponse> {
  return apiFetchUnchecked<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, email, password }),
  });
}

export async function login(
  username: string,
  password: string,
): Promise<AuthResponse> {
  return apiFetchUnchecked<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function getMe(): Promise<AuthUser> {
  return apiFetchUnchecked<AuthUser>("/auth/me");
}

export async function listUsers(): Promise<AuthUser[]> {
  return apiFetchUnchecked<AuthUser[]>("/auth/users");
}

// F1.1b: forgotPassword is migrated through a JsonContract with a runtime
// decoder. The endpoint is public (no auth header needed) but the response
// is validated — a malformed success (missing `message`) is a contract
// failure, not an unchecked cast.
import { callContract, decodeObject, decodeString, type JsonContract } from "./contracts/common";

export interface ForgotPasswordResult {
  message: string;
  reset_token?: string;
}

const forgotPasswordContract: JsonContract<ForgotPasswordResult> = {
  id: "auth.forgotPassword",
  method: "POST",
  pathPattern: "/auth/forgot-password",
  responseKind: "json",
  decoder: decodeObject<ForgotPasswordResult>({
    required: { message: decodeString },
    optional: { reset_token: decodeString },
  }),
};

export async function forgotPassword(email: string): Promise<ForgotPasswordResult> {
  return callContract(forgotPasswordContract, { body: { email } });
}
