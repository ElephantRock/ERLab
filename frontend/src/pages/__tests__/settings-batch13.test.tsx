/**
 * BATCH-13 / TASK-02 — Settings Enhancement Tests
 * TEST-13-02-01 through TEST-13-02-06, TEST-13-02-08
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Settings from "@/pages/settings";
import { SettingsProvider } from "@/contexts/settings-context";
import { AuthProvider } from "@/contexts/auth-context";

// ── Mock API client ─────────────────────────────────────────────────
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
  getEvolutionStatus: vi.fn().mockResolvedValue({ enabled: false, overlays_generated: 0, recent_outcomes: [] }),
}));

vi.mock("@/api/auth", () => ({
  getMe: vi.fn().mockResolvedValue(null),
  listUsers: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/components/settings/model-status-panel", () => ({
  ModelStatusPanel: () => <div data-testid="model-status-panel">Models</div>,
}));

// ── Helper ────────────────────────────────────────────────────────
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
  // Default: detailed status returns valid data
  mockGetDetailedStatus.mockResolvedValue({
    version: "0.1.0",
    provider: "openai",
    db_status: "ok",
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

// ── TEST-13-02-01: Test Connection button calls /health endpoint ──────
it("TEST-13-02-01: Test Connection button calls testConnection", async () => {
  const user = userEvent.setup();
  mockTestConnection.mockResolvedValue({ ok: true, version: "0.1.0" });
  renderSettings();

  // Wait for auto-test on mount to complete
  await waitFor(() => {
    expect(screen.getByTestId("connection-dot").className).toContain("bg-success");
  });

  // Clear calls from auto-test, then test button
  mockTestConnection.mockClear();
  const btn = screen.getByTestId("test-connection-btn");
  await user.click(btn);

  expect(mockTestConnection).toHaveBeenCalledOnce();
});

// ── TEST-13-02-02: Green dot shown when backend is reachable ────────
it("TEST-13-02-02: green dot shown when backend is reachable", async () => {
  const user = userEvent.setup();
  mockTestConnection.mockResolvedValue({ ok: true, version: "0.1.0" });
  renderSettings();

  const btn = screen.getByTestId("test-connection-btn");
  await user.click(btn);

  await waitFor(() => {
    const dot = screen.getByTestId("connection-dot");
    expect(dot.className).toContain("bg-success");
  });
  expect(screen.getByTestId("connection-success")).toHaveTextContent("Connected");
});

// ── TEST-13-02-03: Red dot shown when backend is unreachable ────────
it("TEST-13-02-03: red dot shown when backend is unreachable", async () => {
  const user = userEvent.setup();
  mockTestConnection.mockResolvedValue({ ok: false, error: "Failed to fetch" });
  renderSettings();

  const btn = screen.getByTestId("test-connection-btn");
  await user.click(btn);

  await waitFor(() => {
    const dot = screen.getByTestId("connection-dot");
    expect(dot.className).toContain("bg-destructive");
  });
  expect(screen.getByTestId("connection-error")).toHaveTextContent("Failed to fetch");
});

// ── TEST-13-02-04: Version display shows backend version ─────────────
it("TEST-13-02-04: version display shows backend version from /status/detailed", async () => {
  mockGetDetailedStatus.mockResolvedValue({
    version: "0.2.0",
    provider: "anthropic",
    db_status: "ok",
  });
  renderSettings();

  await waitFor(() => {
    expect(screen.getByTestId("backend-version")).toHaveTextContent("0.2.0");
    expect(screen.getByTestId("backend-provider")).toHaveTextContent("anthropic");
  });
});

// ── TEST-13-02-05: Default domain saved to localStorage ──────────────
it("TEST-13-02-05: default domain saved to localStorage", async () => {
  const user = userEvent.setup();
  renderSettings();

  const input = screen.getByTestId("default-domain-input");
  await user.clear(input);
  await user.type(input, "machine learning");

  expect(localStorage.getItem("erock_default_domain")).toBe("machine learning");
});

// ── TEST-13-02-06: Default domain loaded from localStorage on mount ──
it("TEST-13-02-06: default domain loaded from localStorage on mount", () => {
  localStorage.setItem("erock_default_domain", "quantum computing");
  renderSettings();

  const input = screen.getByTestId("default-domain-input") as HTMLInputElement;
  expect(input.value).toBe("quantum computing");
});

// ── TEST-13-02-08: Settings page calls /status/detailed on mount ─────
it("TEST-13-02-08: settings page calls getDetailedStatus on mount for version", async () => {
  mockGetDetailedStatus.mockResolvedValue({
    version: "0.1.0",
    provider: "openai",
    db_status: "ok",
  });
  renderSettings();

  expect(mockGetDetailedStatus).toHaveBeenCalledOnce();

  await waitFor(() => {
    expect(screen.getByTestId("backend-version")).toHaveTextContent("0.1.0");
  });
});
