/**
 * Tests for centralized auth header injection in client.ts.
 *
 * Verifies:
 * - JWT token is added to API calls via Authorization: Bearer header
 * - API key still works via X-API-Key header
 * - Both headers coexist
 * - Explicit caller headers override defaults
 * - Empty token/key produce no header
 * - No global fetch mutation occurs
 */
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import {
  buildAuthHeaders,
  getJwtToken,
  getApiKey,
  getApiUrl,
} from "@/api/client";

beforeEach(() => {
  localStorage.clear();
});

afterEach(() => {
  localStorage.clear();
});

describe("buildAuthHeaders", () => {
  it("adds JWT Authorization header when token is present", () => {
    localStorage.setItem("erock_jwt_token", "my-jwt-token");
    const headers = buildAuthHeaders();
    expect(headers["Authorization"]).toBe("Bearer my-jwt-token");
  });

  it("adds X-API-Key header when API key is present", () => {
    localStorage.setItem("erock_api_key", "my-api-key");
    const headers = buildAuthHeaders();
    expect(headers["X-API-Key"]).toBe("my-api-key");
  });

  it("both JWT and API key headers coexist", () => {
    localStorage.setItem("erock_jwt_token", "my-jwt-token");
    localStorage.setItem("erock_api_key", "my-api-key");
    const headers = buildAuthHeaders();
    expect(headers["Authorization"]).toBe("Bearer my-jwt-token");
    expect(headers["X-API-Key"]).toBe("my-api-key");
  });

  it("caller-provided extra headers are included", () => {
    localStorage.setItem("erock_jwt_token", "token");
    const headers = buildAuthHeaders({ "Content-Type": "application/json" });
    expect(headers["Content-Type"]).toBe("application/json");
    expect(headers["Authorization"]).toBe("Bearer token");
  });

  it("explicit Authorization header overrides token", () => {
    localStorage.setItem("erock_jwt_token", "stored-token");
    const headers = buildAuthHeaders({ Authorization: "Custom custom" });
    expect(headers["Authorization"]).toBe("Custom custom");
  });

  it("explicit X-API-Key header overrides API key", () => {
    localStorage.setItem("erock_api_key", "stored-key");
    const headers = buildAuthHeaders({ "X-API-Key": "custom-key" });
    expect(headers["X-API-Key"]).toBe("custom-key");
  });

  it("no headers added when neither token nor key is present", () => {
    const headers = buildAuthHeaders();
    expect(headers).toEqual({});
  });

  it("getJwtToken returns empty string when not set", () => {
    expect(getJwtToken()).toBe("");
  });

  it("getJwtToken returns token when set", () => {
    localStorage.setItem("erock_jwt_token", "abc123");
    expect(getJwtToken()).toBe("abc123");
  });

  it("getApiKey returns empty string when not set", () => {
    expect(getApiKey()).toBe("");
  });

  it("getApiUrl returns empty string when not set", () => {
    expect(getApiUrl()).toBe("");
  });

  it("getApiUrl returns URL when set", () => {
    localStorage.setItem("erock_api_url", "http://example.com");
    expect(getApiUrl()).toBe("http://example.com");
  });
});

describe("auth header isolation", () => {
  it("importing client module does not patch window.fetch", () => {
    // The old auth-context.tsx monkey-patched window.fetch at module level.
    // client.ts must NOT have any module-level side effects on fetch.
    // We verify by checking that window.fetch is the native implementation.
    expect(window.fetch.toString()).not.toContain("patchedFetch");
    expect(window.fetch.toString()).not.toContain("erock_jwt_token");
  });
});
