/** Tests for BATCH-28 frontend auth API (TEST-28-02-01, 02, 05, 06, 08). */

import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the client module. F1.3a: listUsers now routes through callContract →
// apiFetchJson; login/register/getMe remain on apiFetchUnchecked. Provide
// both so migrated and non-migrated functions resolve their transport dep.
vi.mock("@/api/client", () => ({
  apiFetchUnchecked: vi.fn(),
  apiFetchJson: vi.fn(),
}));

import { register, login, getMe, listUsers } from "@/api/auth";
import { apiFetchUnchecked, apiFetchJson } from "@/api/client";

const mockApiFetch = vi.mocked(apiFetchUnchecked);
const mockApiFetchJson = vi.mocked(apiFetchJson);

describe("auth API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("TEST-28-02-02: login calls API with correct params", async () => {
    const mockResponse = {
      token: "jwt-token-123",
      user: { id: 1, username: "alice", email: "alice@test.com", role: "user" },
    };
    mockApiFetch.mockResolvedValueOnce(mockResponse);

    const result = await login("alice", "password123");

    expect(mockApiFetch).toHaveBeenCalledWith("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username: "alice", password: "password123" }),
    });
    expect(result.token).toBe("jwt-token-123");
    expect(result.user.username).toBe("alice");
  });

  it("TEST-28-02-05: login success returns token", async () => {
    const mockResponse = {
      token: "jwt-token-456",
      user: { id: 2, username: "bob", email: "bob@test.com", role: "user" },
    };
    mockApiFetch.mockResolvedValueOnce(mockResponse);

    const result = await login("bob", "secret");
    expect(result.token).toBe("jwt-token-456");
  });

  it("TEST-28-02-06: login error throws", async () => {
    mockApiFetch.mockRejectedValueOnce(new Error("Invalid credentials"));

    await expect(login("bob", "wrong")).rejects.toThrow("Invalid credentials");
  });

  it("TEST-28-02-08: register calls API with correct params", async () => {
    const mockResponse = {
      token: "jwt-token-789",
      user: { id: 3, username: "charlie", email: "charlie@test.com", role: "user" },
    };
    mockApiFetch.mockResolvedValueOnce(mockResponse);

    const result = await register("charlie", "charlie@test.com", "pass123");

    expect(mockApiFetch).toHaveBeenCalledWith("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        username: "charlie",
        email: "charlie@test.com",
        password: "pass123",
      }),
    });
    expect(result.user.username).toBe("charlie");
    expect(result.user.role).toBe("user");
  });

  it("getMe calls correct endpoint", async () => {
    const mockUser = { id: 1, username: "alice", email: "alice@test.com", role: "user" };
    mockApiFetch.mockResolvedValueOnce(mockUser);

    const result = await getMe();
    expect(mockApiFetch).toHaveBeenCalledWith("/auth/me");
    expect(result.username).toBe("alice");
  });

  it("listUsers calls correct endpoint", async () => {
    const mockUsers = [
      { id: 1, username: "alice", email: "alice@test.com", role: "admin" },
    ];
    // F1.3a: listUsers now uses callContract → apiFetchJson
    mockApiFetchJson.mockResolvedValueOnce(mockUsers);

    const result = await listUsers();
    expect(mockApiFetchJson).toHaveBeenCalled();
    expect(result).toHaveLength(1);
  });
});
