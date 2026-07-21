import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Settings from "@/pages/settings";
import { SettingsProvider } from "@/contexts/settings-context";
import { AuthProvider } from "@/contexts/auth-context";

// ── Mocks for non-QueryClient dependencies ────────────────────
vi.mock("@/api/client", () => ({
  testConnection: vi.fn().mockResolvedValue({ ok: true, version: "0.1.0" }),
  getDetailedStatus: vi.fn().mockResolvedValue({ version: "0.1.0", provider: "openai", db_status: "ok" }),
  apiFetchUnchecked: vi.fn(),
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
  return render(
    <MemoryRouter>
      <AuthProvider>
        <SettingsProvider>
          <Settings />
        </SettingsProvider>
      </AuthProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
});

describe("Settings", () => {
  // ── TEST-11-01-18: Renders form fields ──────────────────────────
  it("TEST-11-01-18: renders form fields", () => {
    renderSettings();

    expect(screen.getByText("Settings")).toBeInTheDocument();
    expect(screen.getByText("Configure your workspace, models, and preferences.")).toBeInTheDocument();
    expect(screen.getByText("API Connection")).toBeInTheDocument();
    expect(screen.getByText("API Base URL")).toBeInTheDocument();
    expect(screen.getByText("API Key")).toBeInTheDocument();
    expect(screen.getByText("Appearance")).toBeInTheDocument();
    expect(screen.getByText("Light")).toBeInTheDocument();
    expect(screen.getByText("Dark")).toBeInTheDocument();
  });

  // ── TEST-11-01-19: Saves configuration ──────────────────────────
  it("TEST-11-01-19: saves configuration to localStorage", async () => {
    const user = userEvent.setup();
    renderSettings();

    const urlInput = screen.getByPlaceholderText("http://localhost:8000");
    await user.clear(urlInput);
    await user.type(urlInput, "https://api.example.com");

    const keyInput = screen.getByPlaceholderText("Optional API key");
    await user.type(keyInput, "secret-key-123");

    // Check localStorage was updated
    await waitFor(() => {
      expect(localStorage.getItem("erock_api_url")).toBe("https://api.example.com");
    });
    expect(localStorage.getItem("erock_api_key")).toContain("secret-key-123");
  });

  // ── TEST-11-01-20: Shows connection error fallback ──────────────
  it("TEST-11-01-20: renders error when used outside SettingsProvider", () => {
    // Suppress console.error for expected error
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    // Rendering Settings without SettingsProvider should throw
    expect(() => {
      render(
        <MemoryRouter>
          <Settings />
        </MemoryRouter>,
      );
    }).toThrow("useSettings must be used within SettingsProvider");

    consoleSpy.mockRestore();
  });
});
