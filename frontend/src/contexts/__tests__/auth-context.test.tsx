/** Tests for BATCH-28 auth context (TEST-28-02-03, 04, 07). */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { BrowserRouter, MemoryRouter } from "react-router-dom";
import { AuthProvider, useAuth } from "@/contexts/auth-context";

// Mock the auth API
vi.mock("@/api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
  getMe: vi.fn(),
}));

import { login as mockLogin, getMe as mockGetMe } from "@/api/auth";

function ShowAuth() {
  const { user, loading, login, logout } = useAuth();
  if (loading) return <div data-testid="loading">Loading</div>;
  return (
    <div>
      <span data-testid="user-state">{user ? user.username : "null"}</span>
      <button data-testid="login-btn" onClick={() => login("alice", "pass")}>
        Login
      </button>
      <button data-testid="logout-btn" onClick={logout}>
        Logout
      </button>
    </div>
  );
}

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <BrowserRouter>
      <AuthProvider>{ui}</AuthProvider>
    </BrowserRouter>,
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    vi.mocked(mockGetMe).mockReset();
    vi.mocked(mockLogin).mockReset();
    localStorage.clear();
  });

  it("TEST-28-02-03: auth context provides user state", async () => {
    vi.mocked(mockLogin).mockResolvedValue({
      token: "test-token",
      user: { id: 1, username: "alice", email: "a@test.com", role: "user" },
    });

    renderWithProviders(<ShowAuth />);

    // Initially no user (getMe finds no token)
    await waitFor(() => {
      expect(screen.getByTestId("user-state").textContent).toBe("null");
    });

    // Login
    await userEvent.click(screen.getByTestId("login-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("user-state").textContent).toBe("alice");
    });
  });

  it("TEST-28-02-07: logout clears token", async () => {
    vi.mocked(mockLogin).mockResolvedValue({
      token: "test-token",
      user: { id: 1, username: "alice", email: "a@test.com", role: "user" },
    });

    renderWithProviders(<ShowAuth />);

    // Login first
    await userEvent.click(screen.getByTestId("login-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("user-state").textContent).toBe("alice");
    });

    // Logout
    await userEvent.click(screen.getByTestId("logout-btn"));
    await waitFor(() => {
      expect(screen.getByTestId("user-state").textContent).toBe("null");
    });

    // Token cleared from localStorage
    expect(localStorage.getItem("erock_jwt_token")).toBeNull();
  });

  it("restores user from stored token", async () => {
    localStorage.setItem("erock_jwt_token", "existing-token");
    vi.mocked(mockGetMe).mockResolvedValue({
      id: 1,
      username: "restored",
      email: "r@test.com",
      role: "admin",
    });

    renderWithProviders(<ShowAuth />);

    await waitFor(() => {
      expect(screen.getByTestId("user-state").textContent).toBe("restored");
    });
  });
});
