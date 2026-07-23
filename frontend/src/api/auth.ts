/** Auth API client (BATCH-28). */

import { callContract, decodeObject, decodeString, type JsonContract } from "./contracts/common";
import { getMeContract, loginContract, registerContract } from "./contracts/auth";
import { listUsersContract } from "./contracts/f1-3a-reads";

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
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(registerContract, { body: { username, email, password } });
}

export async function login(
  username: string,
  password: string,
): Promise<AuthResponse> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(loginContract, { body: { username, password } });
}

export async function getMe(): Promise<AuthUser> {
  // F1.7a: migrated from apiFetchUnchecked to callContract with runtime decoder.
  return callContract(getMeContract);
}

export async function listUsers(): Promise<AuthUser[]> {
  // F1.3a: migrated from apiFetchUnchecked to callContract with runtime decoder
  return callContract(listUsersContract);
}

// F1.1b: forgotPassword is migrated through a JsonContract with a runtime
// decoder. The endpoint is public (no auth header needed) but the response
// is validated — a malformed success (missing `message`) is a contract
// failure, not an unchecked cast.
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
