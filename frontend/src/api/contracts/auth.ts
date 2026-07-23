/**
 * F1.7a — Auth endpoint contracts (register, login, me).
 *
 * Migrates the three remaining apiFetchUnchecked callers in src/api/auth.ts
 * to JsonContract + runtime decoders. The AuthUser/ AuthResponse shapes are
 * material for auth state: the JWT token gates every subsequent request,
 * the user id drives keying, and `role` gates admin UI (listUsers). All four
 * AuthUser fields are strict-required and role is validated against the
 * closed ("admin" | "user") enum.
 *
 * Backend sources (backend/api/routes/auth.py):
 *   POST /auth/register → AuthResponse { token, user }
 *   POST /auth/login    → AuthResponse { token, user }
 *   GET  /auth/me       → UserResponse { id, username, email, role }
 */

import type { AuthResponse, AuthUser } from "@/api/auth";
import {
  decodeEnum,
  decodeNumber,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./common";

// AuthUser — all four fields are material. role is a closed enum.
const authUserDecoder = decodeObject<AuthUser>({
  required: {
    id: decodeNumber,
    username: decodeString,
    email: decodeString,
    role: decodeEnum<AuthUser["role"]>(["admin", "user"]),
  },
});

// AuthResponse — token gates every request, user drives auth state.
const authResponseDecoder = decodeObject<AuthResponse>({
  required: {
    token: decodeString,
    user: authUserDecoder,
  },
});

// ── Contracts ────────────────────────────────────────────────────────

export const registerContract: JsonContract<AuthResponse> = {
  id: "auth.register",
  method: "POST",
  pathPattern: "/auth/register",
  responseKind: "json",
  decoder: authResponseDecoder,
};

export const loginContract: JsonContract<AuthResponse> = {
  id: "auth.login",
  method: "POST",
  pathPattern: "/auth/login",
  responseKind: "json",
  decoder: authResponseDecoder,
};

export const getMeContract: JsonContract<AuthUser> = {
  id: "auth.getMe",
  method: "GET",
  pathPattern: "/auth/me",
  responseKind: "json",
  decoder: authUserDecoder,
};
