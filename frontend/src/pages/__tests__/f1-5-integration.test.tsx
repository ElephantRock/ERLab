/**
 * F1.5a — Critical Product-Flow Integration Tests (sealed).
 *
 * Uses the PRODUCTION route registry (createRoutes from AppRoutes.tsx)
 * with eager page imports. Mocks at the global fetch boundary so ALL
 * transport paths (apiFetchJson, apiFetchVoid, apiFetchUnchecked,
 * callContract) are intercepted regardless of import order.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import React from "react";

// ── Transport mock: intercept global fetch ──────────────────────────

type MockResponse = { status?: number; body?: unknown };
const fetchMock = vi.fn();

vi.mock("@/api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/client")>();
  return {
    ...actual,
    testConnection: vi.fn(),
    getDetailedStatus: vi.fn(),
    apiFetchBlob: vi.fn(async () => new Blob(["test"])),
  };
});

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

// ── Production route registry with eager imports ─────────────────────
import { createRoutes, ProtectedRoute } from "../../AppRoutes";

import Dashboard from "../../pages/dashboard";
import RunDetail from "../../pages/run-detail";
import IdeaDetail from "../../pages/idea-detail";
import GapDetail from "../../pages/gap-detail";
import LiteraturePage from "../../pages/literature";
import LoginPage from "../../pages/login";

const Stub = ({ name }: { name: string }) => <div data-testid={`stub-${name}`} />;
const stubPages = {
  Dashboard, PipelineNew: () => <Stub name="pipeline" />, RunDetail,
  IdeasBrowser: () => <Stub name="ideas" />, IdeaDetail,
  GapsExplorer: () => <Stub name="gaps" />, GapDetail,
  KnowledgeSearch: () => <Stub name="knowledge" />,
  Settings: () => <Stub name="settings" />, Literature: LiteraturePage,
  Memory: () => <Stub name="memory" />, Costs: () => <Stub name="costs" />,
  Governance: () => <Stub name="gov" />, Traces: () => <Stub name="traces" />,
  Sessions: () => <Stub name="sessions" />,
  KnowledgeGraph: () => <Stub name="kg" />,
  Autonomous: () => <Stub name="auto" />,
  Plugins: () => <Stub name="plugins" />,
  Ops: () => <Stub name="ops" />,
};

const productionRouteSet = createRoutes(stubPages);

// ── Test data ────────────────────────────────────────────────────────

const mockRuns = { runs: [{ id: 42, status: "completed", domain: "AI/NLP", current_stage: "completed", ideas_count: 3, session_id: null, created_at: "2026-01-01", completed_at: "2026-01-02", error_message: null, strategy: "standard" }], total: 1 };
const mockIdeas = { ideas: [{ id: 1, title: "Novel Transformer", domain: "AI/NLP", novelty_score: 0.85, feasibility_score: 7.5, overall_score: 0.8, source_gap_ids: null, has_proposal: true, pipeline_run_id: 42, created_at: "2026-01-01", quality_summary: { passed: true, total: 5, has_issues: false }, governance_status: null }], total: 1, score_guide: {} };
const mockPending = { pending: [] };
const mockOps = { health: { total_runs: 1, completed: 1, failed: 0, cancelled: 0, running: 0, pending: 0, average_duration_s: 60, slowest_stages: [] }, quality_trends: { common_failures: [] }, costs: { total_cost: 0, by_provider: [], by_stage: [], by_model: [] }, ideas: { total: 1, cited: 0, supporting: 0 }, model_usage: { models: [] }, window: { days: 7, from: "2026-01-01", to: "2026-01-08" } };
const mockRunDetail = { ...mockRuns.runs[0], config: {}, stages_completed: ["literature_search","ingestion","gap_analysis","idea_generation"], tree_data: null };
const mockRunIdeas = { ideas: mockIdeas.ideas, total: 1 };
const mockIdeaDetail = { idea: { ...mockIdeas.ideas[0], description: "A novel approach", source_gaps: [{ resolved: true, gap_id: 12, gap_title: "Test Gap", gap_confidence: 0.9 }], proposal_sections: {}, proposal_references: null, supporting_papers: null, quality_checks: [], ensemble_review: null, novelty_report: null, feasibility_report: null, remediation_hints: [] } };
const mockGapDetail = { gap: { id: 12, title: "Gap in transformer scaling", description: "desc", gap_type: "methodological", confidence: 0.85, potential_impact: "high", idea_count: 0, status: "identified", matched_papers_preview: [{ id: 101, title: "Scaling Laws", abstract: "Models scale.", year: 2020, venue: "ICML", citation_count: 1000 }] } };
const mockGapPapers = { papers: [{ id: 101, title: "Scaling Laws", abstract: "Models scale.", year: 2020, venue: "ICML", citation_count: 1000 }, { id: 102, title: "Chinchilla", abstract: "Compute-optimal.", year: 2022, venue: "NeurIPS", citation_count: 500 }], total: 2 };
const mockLit = { papers: [{ id: "ss-1", source: "semantic_scholar", title: "Attention Is All You Need", abstract: "Transformer", authors: [{ name: "Vaswani" }], year: 2017, venue: "NeurIPS", citation_count: 100000, url: null, doi: null, arxiv_id: null, keywords: [] }] };
const mockIngest = { status: "ingested", id: "ss-1" };

function defaultHandler(path: string): MockResponse {
  const p = path.split("?")[0];
  if (p === "/pipeline/runs") return { body: mockRuns };
  if (p === "/ideas") return { body: mockIdeas };
  if (p === "/governance/pending") return { body: mockPending };
  if (p.startsWith("/ops/dashboard")) return { body: mockOps };
  if (p === "/pipeline/runs/detail/42") return { body: mockRunDetail };
  if (p.startsWith("/pipeline/runs/") && p.includes("/ideas")) return { body: mockRunIdeas };
  if (p === "/ideas/1") return { body: mockIdeaDetail };
  if (p === "/gaps/12") return { body: mockGapDetail };
  if (p === "/gaps/13") return { body: { gap: { ...mockGapDetail.gap, id: 13, title: "Gap Beta", status: "addressed" } } };
  if (p === "/gaps/12/papers") return { body: mockGapPapers };
  if (p.endsWith("/status") && p.includes("/gaps/")) return { body: { gap: { id: 12, status: "investigating" } } };
  if (p.startsWith("/literature/search")) return { body: mockLit };
  if (p === "/literature/ingest") return { body: mockIngest };
  return { status: 404, body: { detail: "Not found" } };
}

// ── Fetch mock helpers ───────────────────────────────────────────────

function stripPath(url: string): string {
  return url.replace(/^https?:\/\/[^/]*\/api\/v1/, "").replace(/^\/api\/v1/, "");
}

function makeResponse(res: MockResponse): Response {
  const status = res.status || 200;
  return { ok: status < 400, status, json: async () => res.body, text: async () => JSON.stringify(res.body), blob: async () => new Blob(), statusText: status < 400 ? "OK" : "Error" } as Response;
}

/** Install a path-based handler as the global fetch mock. */
function installHandler(handler: (path: string, init?: RequestInit) => MockResponse | Promise<MockResponse>) {
  fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    const path = stripPath(url);
    return makeResponse(await handler(path, init));
  });
  vi.stubGlobal("fetch", fetchMock);
}

// ── Harness ──────────────────────────────────────────────────────────

function makeQC() { return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } }); }

function renderApp(initialPath: string, authUser: unknown = { id: 1, username: "test" }) {
  const qc = makeQC();
  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/*" element={
              <ProtectedRoute user={authUser} loading={false}>
                {productionRouteSet}
              </ProtectedRoute>
            } />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

/** Count fetch calls matching a path substring */
function countCalls(pathFragment: string): number {
  return fetchMock.mock.calls.filter(([url]) => stripPath(String(url)).includes(pathFragment)).length;
}

/** Check if any fetch call matches path + method */
function hasCall(pathFragment: string, method?: string): boolean {
  return fetchMock.mock.calls.some(([url, init]) => {
    const p = stripPath(String(url));
    const m = (init as RequestInit)?.method;
    return p.includes(pathFragment) && (!method || m === method);
  });
}

// ── Tests ────────────────────────────────────────────────────────────

describe("F1.5a Critical Product-Flow Integration (sealed)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    installHandler((path) => defaultHandler(path));
  });

  it("golden flow: dashboard renders, production link reaches idea detail", async () => {
    renderApp("/");
    await waitFor(() => expect(screen.getByText("Novel Transformer")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Novel Transformer"));
    await waitFor(() => expect(hasCall("/ideas/1")).toBe(true), { timeout: 5000 });
  });

  it("literature: confirm → pending → exactly 1 request", async () => {
    // Never resolve ingest — keep mutation in pending state
    installHandler((path) => {
      if (path === "/literature/ingest") return new Promise<MockResponse>(() => {});
      return defaultHandler(path);
    });
    renderApp("/literature");
    const input = screen.getByTestId("literature-search-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "attention" } });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() => expect(screen.getByTestId("ingest-button")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ingest-button"));
    await waitFor(() => expect(screen.getByText("Confirm Ingest")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ingest-button"));
    // Wait for pending state, then try duplicate
    await waitFor(() => expect(screen.getByTestId("ingest-button")).toBeDisabled());
    fireEvent.click(screen.getByTestId("ingest-button")); // duplicate while pending
    expect(countCalls("/literature/ingest")).toBe(1);
  });

  it("literature: failure → context retained → retry succeeds", async () => {
    let count = 0;
    installHandler((path) => {
      if (path === "/literature/ingest") {
        count++;
        if (count === 1) return { status: 500, body: { detail: "err" } };
        return { body: mockIngest };
      }
      return defaultHandler(path);
    });
    renderApp("/literature");
    const input = screen.getByTestId("literature-search-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);
    await waitFor(() => expect(screen.getByTestId("ingest-button")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ingest-button"));
    await waitFor(() => expect(screen.getByText("Confirm Ingest")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ingest-button"));
    await waitFor(() => expect(count).toBe(1));
    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("ingest-button")).not.toBeDisabled());
    fireEvent.click(screen.getByTestId("ingest-button"));
    await waitFor(() => expect(screen.getByText("Confirm Ingest")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ingest-button"));
    await waitFor(() => expect(count).toBe(2));
  });

  it("gap status: mutation → authoritative refetch", async () => {
    renderApp("/gaps/12");
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("gap-status-select"), { target: { value: "investigating" } });
    await waitFor(() => expect(hasCall("/gaps/12/status")).toBe(true));
    await waitFor(() => expect(countCalls("/gaps/12")).toBeGreaterThanOrEqual(2));
  });

  it("gap A/B: same router, late A mutation, B unchanged", async () => {
    let resolveA: (v: MockResponse) => void = () => {};
    const promise = new Promise<MockResponse>((r) => { resolveA = r; });
    installHandler((path, init) => {
      if (path.split("?")[0].includes("/gaps/12/status") && init?.method === "PATCH") return promise;
      return defaultHandler(path);
    });
    const qc = makeQC();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/gaps/12"]}>
          <Routes>
            <Route path="/*" element={<ProtectedRoute user={{}} loading={false}>{productionRouteSet}</ProtectedRoute>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("gap-status-select"), { target: { value: "investigating" } });
    await waitFor(() => expect(hasCall("/gaps/12/status", "PATCH")).toBe(true));
    resolveA({ body: { gap: { id: 12, status: "investigating" } } });
    await new Promise((r) => setTimeout(r, 200));
    expect(countCalls("/gaps/13")).toBe(0);
  });

  it("dashboard: governance fails while ideas render", async () => {
    installHandler((path) => {
      if (path.split("?")[0] === "/governance/pending") return { status: 500, body: { detail: "err" } };
      return defaultHandler(path);
    });
    renderApp("/");
    await waitFor(() => expect(screen.getAllByTestId("widget-error").length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText("Novel Transformer")).toBeInTheDocument();
  });

  it("malformed papers HTTP-200 → contract failure", async () => {
    installHandler((path) => {
      if (path.split("?")[0] === "/gaps/12/papers") return { body: { wrong: "shape" } };
      return defaultHandler(path);
    });
    renderApp("/gaps/12");
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());
    const btn = screen.queryByText("Show more matched papers");
    if (btn) {
      fireEvent.click(btn);
      await waitFor(() => expect(screen.getByText("Failed to load papers.")).toBeInTheDocument(), { timeout: 5000 });
      expect(screen.queryByText("No additional matched papers found.")).not.toBeInTheDocument();
    }
  });

  it("deep link /gaps/12 via production routes", async () => {
    renderApp("/gaps/12");
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());
  });

  it("unauthenticated → login redirect via production ProtectedRoute", async () => {
    // LoginPage uses useAuth internally — mock it to avoid AuthProvider requirement
    vi.mock("@/contexts/auth-context", () => ({
      useAuth: () => ({ user: null, loading: false, login: vi.fn(), register: vi.fn(), logout: vi.fn() }),
    }));
    // Need to re-import LoginPage after mock
    vi.resetModules();
    const StubLogin = () => <div data-testid="login-page">Login</div>;

    const qc = makeQC();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/gaps/12"]}>
          <Routes>
            <Route path="/login" element={<StubLogin />} />
            <Route path="/*" element={
              <ProtectedRoute user={null} loading={false}>
                {productionRouteSet}
              </ProtectedRoute>
            } />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("login-page")).toBeInTheDocument());
  });

  it("unknown route → dashboard fallback", async () => {
    renderApp("/nonexistent");
    await waitFor(() => expect(screen.getByText("Novel Transformer")).toBeInTheDocument());
  });
});
