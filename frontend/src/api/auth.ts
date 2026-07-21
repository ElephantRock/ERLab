/** Auth API client (BATCH-28). */

import { apiFetch } from "./client";

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
  return apiFetch<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, email, password }),
  });
}

export async function login(
  username: string,
  password: string,
): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function getMe(): Promise<AuthUser> {
  return apiFetch<AuthUser>("/auth/me");
}

export async function listUsers(): Promise<AuthUser[]> {
  return apiFetch<AuthUser[]>("/auth/users");
}

// F1.1a-1: forgotPassword migrates the raw fetch() in login.tsx through the
// canonical transport (apiFetch). The endpoint is public (no auth header
// needed) but routing through apiFetch gives consistent error normalization,
// status handling, and future auth-policy flexibility.
export interface ForgotPasswordResponse {
  message: string;
  reset_token?: string;
}

export async function forgotPassword(email: string): Promise<ForgotPasswordResponse> {
  return apiFetch<ForgotPasswordResponse>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}
