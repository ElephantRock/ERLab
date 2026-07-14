/**
 * Phase 4: Settings & Model Visibility tests
 *
 * Covers:
 * - Settings sections render correctly (Connection, Models, Defaults, etc.)
 * - Auto-test connection on mount
 * - Connection health with latency display
 * - Advanced section collapse/expand
 * - Self-improvement remains in Advanced
 * - Admin-only user management gated
 * - Session info in defaults
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Settings from "@/pages/settings";
import { SettingsProvider } from "@/contexts/settings-context";
import { AuthProvider } from "@/contexts/auth-context";

// ── Polyfills ──────────────────────────────────────────────────
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

// ── Mocks ──────────────────────────────────────────────────────
const mockTestConnection = vi.fn();
const mockGetDetailedStatus = vi.fn();

vi.mock("@/api/client", () => ({
  testConnection: (...args: unknown[]) => mockTestConnection(...args),
  getDetailedStatus: (...args: unknown[]) => mockGetDetailedStatus(...args),
  apiFetch: vi.fn(),
  getApiUrl: () => "",
  getApiKey: () => "",
  buildUrl: (path: string) => `/api/v1${path}`,
  buildAuthHeaders: () => ({}),
}));

vi.mock("@/api/autonomous", () => ({
  getEvolutionStatus: vi.fn().mockResolvedValue({
    enabled: false,
    overlays_generated: 0,
    recent_outcomes: [],
  }),
}));

vi.mock("@/api/auth", () => ({
  getMe: vi.fn().mockResolvedValue(null),
  listUsers: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/components/settings/model-status-panel", () => ({
  ModelStatusPanel: () => <div data-testid="model-status-panel">Models</div>,
}));

function renderSettings() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0, staleTime: 0 } },
  });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthProvider>
          <SettingsProvider>
            <Settings />
          </SettingsProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  mockTestConnection.mockResolvedValue({ ok: true, version: "0.1.0" });
  mockGetDetailedStatus.mockResolvedValue({
    version: "0.1.0",
    provider: "openai",
    db_status: "ok",
  });
});

describe("Phase 4: Settings sections", () => {
  it("renders all main sections", async () => {
    renderSettings();

    expect(screen.getByText("API Connection")).toBeInTheDocument();
    expect(screen.getByText("Defaults")).toBeInTheDocument();
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Help & Onboarding")).toBeInTheDocument();
    expect(screen.getByText("Advanced")).toBeInTheDocument();
  });

  it("renders models section with ModelStatusPanel", async () => {
    renderSettings();

    await waitFor(() => {
      expect(screen.getByTestId("models-section")).toBeInTheDocument();
      expect(screen.getByTestId("model-status-panel")).toBeInTheDocument();
    });
  });

  it("renders backend DB status", async () => {
    renderSettings();

    await waitFor(() => {
      expect(screen.getByTestId("backend-db-status")).toHaveTextContent("ok");
    });
  });

  it("shows current session in defaults", async () => {
    localStorage.setItem("erock_session_id", "test-session-abc");
    renderSettings();

    await waitFor(() => {
      const sessionEl = screen.getByTestId("current-session");
      expect(sessionEl).toHaveValue("test-session-abc");
    });
  });

  it("shows (none) when no session is set", async () => {
    renderSettings();

    await waitFor(() => {
      const sessionEl = screen.getByTestId("current-session");
      expect(sessionEl).toHaveValue("(none)");
    });
  });
});

describe("Phase 4: Connection auto-test", () => {
  it("auto-tests connection on mount", async () => {
    renderSettings();

    await waitFor(() => {
      expect(mockTestConnection).toHaveBeenCalledTimes(1);
    });
  });

  it("shows latency when connected", async () => {
    renderSettings();

    await waitFor(() => {
      expect(screen.getByTestId("connection-success")).toBeInTheDocument();
    });
    // Latency should be displayed (just check it exists, not the value)
    expect(screen.getByText(/ms/)).toBeInTheDocument();
  });

  it("shows error state when connection fails on mount", async () => {
    mockTestConnection.mockResolvedValue({
      ok: false,
      error: "Connection refused",
    });

    renderSettings();

    await waitFor(() => {
      expect(screen.getByTestId("connection-error")).toHaveTextContent(
        "Connection refused",
      );
    });
  });
});

describe("Phase 4: Advanced section", () => {
  it("is collapsed by default", () => {
    renderSettings();

    expect(screen.queryByTestId("self-improve-section")).not.toBeInTheDocument();
  });

  it("expands to show Self-Improvement", async () => {
    renderSettings();

    const toggle = screen.getByTestId("advanced-toggle");
    fireEvent.click(toggle);

    await waitFor(() => {
      expect(screen.getByTestId("self-improve-section")).toBeInTheDocument();
    });
  });

  it("shows evolution status when expanded", async () => {
    renderSettings();

    fireEvent.click(screen.getByTestId("advanced-toggle"));

    await waitFor(() => {
      expect(screen.getByTestId("evolution-enabled-status")).toHaveTextContent(
        "Disabled",
      );
    });
  });

  it("does not show user management for non-admin users", async () => {
    renderSettings();

    fireEvent.click(screen.getByTestId("advanced-toggle"));

    await waitFor(() => {
      expect(screen.queryByTestId("user-management-section")).not.toBeInTheDocument();
    });
  });

  it("can collapse again after expanding", async () => {
    renderSettings();

    const toggle = screen.getByTestId("advanced-toggle");
    fireEvent.click(toggle);
    await waitFor(() =>
      expect(screen.getByTestId("self-improve-section")).toBeInTheDocument(),
    );

    fireEvent.click(toggle);
    await waitFor(() =>
      expect(screen.queryByTestId("self-improve-section")).not.toBeInTheDocument(),
    );
  });
});
