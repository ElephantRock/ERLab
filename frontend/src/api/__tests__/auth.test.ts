/** Tests for BATCH-28 frontend auth API (TEST-28-02-01, 02, 05, 06, 08). */

import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock the client module
const mockFetch = vi.fn();
vi.mock("@/api/client", () => ({
  apiFetchUnchecked: (...args: unknown[]) => mockFetch(...args),
}));

import { register, login, getMe, listUsers } from "@/api/auth";

describe("auth API", () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it("TEST-28-02-02: login calls API with correct params", async () => {
    const mockResponse = {
      token: "jwt-token-123",
      user: { id: 1, username: "alice", email: "alice@test.com", role: "user" },
    };
    mockFetch.mockResolvedValue(mockResponse);

    const result = await login("alice", "password123");

    expect(mockFetch).toHaveBeenCalledWith("/auth/login", {
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
    mockFetch.mockResolvedValue(mockResponse);

    const result = await login("bob", "secret");
    expect(result.token).toBe("jwt-token-456");
  });

  it("TEST-28-02-06: login error throws", async () => {
    mockFetch.mockRejectedValue(new Error("Invalid credentials"));

    await expect(login("bob", "wrong")).rejects.toThrow("Invalid credentials");
  });

  it("TEST-28-02-08: register calls API with correct params", async () => {
    const mockResponse = {
      token: "jwt-token-789",
      user: { id: 3, username: "charlie", email: "charlie@test.com", role: "user" },
    };
    mockFetch.mockResolvedValue(mockResponse);

    const result = await register("charlie", "charlie@test.com", "pass123");

    expect(mockFetch).toHaveBeenCalledWith("/auth/register", {
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
    mockFetch.mockResolvedValue(mockUser);

    const result = await getMe();
    expect(mockFetch).toHaveBeenCalledWith("/auth/me");
    expect(result.username).toBe("alice");
  });

  it("listUsers calls correct endpoint", async () => {
    const mockUsers = [
      { id: 1, username: "alice", email: "alice@test.com", role: "admin" },
    ];
    mockFetch.mockResolvedValue(mockUsers);

    const result = await listUsers();
    expect(mockFetch).toHaveBeenCalledWith("/auth/users");
    expect(result).toHaveLength(1);
  });
});
