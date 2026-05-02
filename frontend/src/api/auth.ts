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
