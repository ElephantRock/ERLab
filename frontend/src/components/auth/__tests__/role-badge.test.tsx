/** Tests for BATCH-28 role badge and user management (TEST-28-03-01, 02, 03). */

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RoleBadge } from "@/components/auth/role-badge";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/contexts/auth-context";
import { SettingsProvider } from "@/contexts/settings-context";

// Mock auth API
vi.mock("@/api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
  getMe: vi.fn().mockResolvedValue(null),
  listUsers: vi.fn().mockResolvedValue([
    { id: 1, username: "admin", email: "admin@test.com", role: "admin" },
    { id: 2, username: "user1", email: "user1@test.com", role: "user" },
  ]),
}));

// Mock other APIs used by settings
vi.mock("@/api/client", () => ({
  testConnection: vi.fn().mockResolvedValue({ ok: true, version: "0.1.0" }),
  getDetailedStatus: vi.fn().mockRejectedValue("not available"),
  getApiUrl: () => "",
  getApiKey: () => "",
  buildUrl: (p: string) => p,
  buildAuthHeaders: () => ({}),
  apiFetchUnchecked: vi.fn(),
}));

vi.mock("@/api/autonomous", () => ({
  getEvolutionStatus: vi.fn().mockRejectedValue("not available"),
}));

vi.mock("@/components/settings/model-status-panel", () => ({
  ModelStatusPanel: () => <div data-testid="model-status-panel">Models</div>,
}));

import SettingsPage from "@/pages/settings";

function renderWithProviders(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <SettingsProvider>
          <AuthProvider>{ui}</AuthProvider>
        </SettingsProvider>
      </BrowserRouter>
    </QueryClientProvider>,
  );
}

describe("RoleBadge", () => {
  it("TEST-28-03-03: role badge shows correct role", () => {
    const { rerender } = render(<RoleBadge role="admin" />);
    expect(screen.getByTestId("role-badge-admin")).toBeInTheDocument();
    expect(screen.getByTestId("role-badge-admin").textContent).toBe("admin");

    rerender(<RoleBadge role="user" />);
    expect(screen.getByTestId("role-badge-user")).toBeInTheDocument();
    expect(screen.getByTestId("role-badge-user").textContent).toBe("user");
  });
});

describe("User Management in Settings", () => {
  it("TEST-28-03-01: admin sees user management section", async () => {
    const { getMe } = await import("@/api/auth");
    vi.mocked(getMe).mockResolvedValue({
      id: 1,
      username: "admin",
      email: "admin@test.com",
      role: "admin",
    });
    localStorage.setItem("erock_jwt_token", "fake-token");

    renderWithProviders(<SettingsPage />);

    // Wait for settings to load, then expand Advanced
    await screen.findByTestId("advanced-toggle", undefined, { timeout: 3000 });
    fireEvent.click(screen.getByTestId("advanced-toggle"));

    await screen.findByTestId("user-management-section", undefined, {
      timeout: 3000,
    });
  });

  it("TEST-28-03-02: non-admin user does not see user management", async () => {
    const { getMe } = await import("@/api/auth");
    vi.mocked(getMe).mockResolvedValue({
      id: 2,
      username: "regular",
      email: "regular@test.com",
      role: "user",
    });
    localStorage.setItem("erock_jwt_token", "fake-token");

    renderWithProviders(<SettingsPage />);

    await screen.findByTestId("test-connection-btn", undefined, {
      timeout: 3000,
    });

    expect(screen.queryByTestId("user-management-section")).not.toBeInTheDocument();
  });
});
