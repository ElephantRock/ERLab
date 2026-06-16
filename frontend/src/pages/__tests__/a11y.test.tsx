/**
 * Accessibility tests for key pages (BATCH-52, TASK-01).
 * Uses jest-axe to check WCAG 2.1 AA compliance.
 * Color-contrast is disabled since jsdom doesn't compute real CSS.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { SettingsProvider } from "@/contexts/settings-context";
import { AuthProvider } from "@/contexts/auth-context";
import { checkA11y } from "@/test/a11y-test-utils";

// ── JSDOM polyfills for Radix UI ─────────────────────────────────
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

class IntersectionObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.IntersectionObserver = IntersectionObserverMock as unknown as typeof IntersectionObserver;

Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// ── Mock API modules (AR-03: no real HTTP) ──────────────────────

// Dashboard mocks
vi.mock("@/api/status", () => ({
  getSystemStatus: vi.fn().mockResolvedValue({
    app_name: "Elephant Rock",
    version: "1.0.0",
    config: {},
    defaults: {},
  }),
}));

vi.mock("@/api/pipeline", () => ({
  listRuns: vi.fn().mockResolvedValue({ runs: [], total: 0 }),
  triggerRun: vi.fn(),
}));

vi.mock("@/api/ideas", () => ({
  listIdeas: vi.fn().mockResolvedValue({ ideas: [], total: 0, score_guide: {} }),
}));

vi.mock("@/api/gaps", () => ({
  listGaps: vi.fn().mockResolvedValue({ gaps: [], total: 0 }),
}));

vi.mock("@/api/knowledge", () => ({
  searchKnowledge: vi.fn().mockResolvedValue({ query: "", results: [] }),
  getKnowledgeStats: vi.fn().mockResolvedValue({ total_documents: 0, total_chunks: 0 }),
}));

vi.mock("@/api/auth", () => ({
  login: vi.fn(),
  register: vi.fn(),
  getMe: vi.fn().mockResolvedValue(null),
  listUsers: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/api/client", () => ({
  testConnection: vi.fn().mockResolvedValue({ ok: true }),
  getDetailedStatus: vi.fn().mockResolvedValue(null),
  apiFetch: vi.fn().mockResolvedValue({ clusters: [], total_papers: 0 }),
  getApiUrl: () => "",
  getApiKey: () => "",
  buildUrl: (p: string) => p,
  buildAuthHeaders: () => ({}),
}));

vi.mock("@/api/autonomous", () => ({
  getEvolutionStatus: vi.fn().mockResolvedValue(null),
}));

// ── Mock lazy-loaded charts to avoid recharts canvas issues ─────
vi.mock("@/components/charts/score-distribution", () => ({
  ScoreDistributionChart: () => <div data-testid="score-chart" />,
}));
vi.mock("@/components/charts/domain-breakdown", () => ({
  DomainBreakdownChart: () => <div data-testid="domain-chart" />,
}));
vi.mock("@/components/charts/run-status-chart", () => ({
  RunStatusChart: () => <div data-testid="status-chart" />,
}));

// ── Mock complex child components ────────────────────────────────
vi.mock("@/components/pipeline/run-card", () => ({
  RunCard: ({ run }: { run: any }) => (
    <div data-testid="run-card">{run.domain}</div>
  ),
}));

vi.mock("@/components/ideas/idea-card", () => ({
  IdeaCard: ({ idea }: { idea: any }) => (
    <div data-testid="idea-card">{idea.title}</div>
  ),
}));

vi.mock("@/components/gaps/gap-card", () => ({
  GapCard: ({ gap }: { gap: any }) => (
    <div data-testid="gap-card">{gap.title}</div>
  ),
}));

vi.mock("@/components/gaps/cluster-scatter", () => ({
  ClusterScatterPlot: () => <div data-testid="cluster-scatter" />,
}));

vi.mock("@/components/knowledge/upload-zone", () => ({
  UploadZone: ({ onUploadSuccess }: { onUploadSuccess: () => void }) => (
    <div data-testid="upload-zone">Upload</div>
  ),
}));

vi.mock("@/components/export/export-dialog", () => ({
  ExportDialog: ({ ideaIds }: { ideaIds: number[] }) => (
    <div data-testid="export-dialog">Export {ideaIds.length}</div>
  ),
}));

vi.mock("@/components/auth/role-badge", () => ({
  RoleBadge: ({ role }: { role: string }) => (
    <span data-testid="role-badge">{role}</span>
  ),
}));

// ── Helper ──────────────────────────────────────────────────────
function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

function wrapWithQueryProvider(ui: React.ReactElement) {
  const qc = createQueryClient();
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

function wrapWithAuthProvider(ui: React.ReactElement) {
  return (
    <MemoryRouter>
      <AuthProvider>{ui}</AuthProvider>
    </MemoryRouter>
  );
}

function wrapWithFullProviders(ui: React.ReactElement) {
  const qc = createQueryClient();
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthProvider>
          <SettingsProvider>{ui}</SettingsProvider>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
});

// ── A11y Tests ──────────────────────────────────────────────────

describe("Accessibility (WCAG 2.1 AA)", () => {
  // 1. Dashboard
  it("TEST-52-01: Dashboard has no a11y violations", async () => {
    const Dashboard = (await import("@/pages/dashboard")).default;
    await checkA11y(wrapWithQueryProvider(<Dashboard />));
  });

  // 2. Ideas Browser
  it("TEST-52-02: Ideas Browser has no a11y violations", async () => {
    const IdeasBrowser = (await import("@/pages/ideas-browser")).default;
    await checkA11y(wrapWithQueryProvider(<IdeasBrowser />));
  });

  // 3. Gaps Explorer
  it("TEST-52-03: Gaps Explorer has no a11y violations", async () => {
    const GapsExplorer = (await import("@/pages/gaps-explorer")).default;
    await checkA11y(wrapWithQueryProvider(<GapsExplorer />));
  });

  // 4. Settings
  it("TEST-52-04: Settings has no a11y violations", async () => {
    const Settings = (await import("@/pages/settings")).default;
    await checkA11y(wrapWithFullProviders(<Settings />));
  });

  // 5. Login
  it("TEST-52-05: Login has no a11y violations", async () => {
    const LoginPage = (await import("@/pages/login")).default;
    await checkA11y(
      wrapWithAuthProvider(
        <Routes>
          <Route path="/" element={<LoginPage />} />
        </Routes>,
      ),
    );
  });

  // 6. Knowledge Search
  it("TEST-52-06: Knowledge Search has no a11y violations", async () => {
    const KnowledgeSearch = (await import("@/pages/knowledge-search")).default;
    await checkA11y(wrapWithQueryProvider(<KnowledgeSearch />));
  });
});
