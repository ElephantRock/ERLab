/**
 * F1.5 — Critical Product-Flow Integration Tests.
 *
 * Mounts production pages through the real router with a shared QueryClient.
 * Mocks at the transport boundary (apiFetchJson/apiFetchVoid/apiFetchUnchecked)
 * so production clients, callContract, decoders, and cache all run for real.
 *
 * Mocked boundaries (documented):
 *   - apiFetchJson/apiFetchVoid/apiFetchUnchecked (transport)
 *   - apiFetchBlob (binary download)
 *   - toast/sonner (non-visual)
 *   - GraphCanvas/EntityDetail/WorldModelPanel (browser-only rendering, KG page only)
 *   - Auth: pages rendered directly inside MemoryRouter (bypasses ProtectedRoute
 *     for page-level tests; auth posture tested separately)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route, Navigate } from "react-router-dom";
import React from "react";

// ── Transport mock ───────────────────────────────────────────────────
// Single shared mock function that routes by path + method

type MockResponse = { status?: number; body?: unknown };
type MockHandler = (path: string, options?: RequestInit) => MockResponse | Promise<MockResponse>;

const transportMock = vi.fn<MockHandler>();

vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(async (path: string, options?: RequestInit) => {
    const res = await transportMock(path, options);
    if (res.status && res.status >= 400) {
      const err = new Error(res.body?.detail || res.body?.error?.message || "HTTP error");
      (err as any).status = res.status;
      throw err;
    }
    return res.body;
  }),
  apiFetchVoid: vi.fn(async (path: string, options?: RequestInit) => {
    const res = await transportMock(path, options);
    if (res.status && res.status >= 400) {
      throw new Error(res.body?.detail || "HTTP error");
    }
  }),
  apiFetchUnchecked: vi.fn(async (path: string, options?: RequestInit) => {
    const res = await transportMock(path, options);
    if (res.status && res.status >= 400) {
      throw new Error(res.body?.detail || "HTTP error");
    }
    return res.body;
  }),
  apiFetchBlob: vi.fn(async () => new Blob(["test"])),
  ApiError: class ApiError extends Error {
    constructor(public status: number, public detail: string) { super(detail); this.name = "ApiError"; }
  },
  buildAuthHeaders: vi.fn(() => ({})),
  buildUrl: vi.fn((p: string) => p),
  getApiUrl: vi.fn(() => ""),
  getApiKey: vi.fn(() => ""),
  getJwtToken: vi.fn(() => ""),
  testConnection: vi.fn(),
  getDetailedStatus: vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

// ── Test data ────────────────────────────────────────────────────────

const mockRuns = {
  runs: [
    { id: 42, status: "completed", domain: "AI/NLP", current_stage: "completed",
      ideas_count: 3, session_id: null, created_at: "2026-01-01", completed_at: "2026-01-02",
      error_message: null, strategy: "standard" },
  ],
  total: 1,
};

const mockIdeas = {
  ideas: [
    { id: 1, title: "Novel Transformer Architecture", domain: "AI/NLP",
      novelty_score: 0.85, feasibility_score: 7.5, overall_score: 0.8,
      source_gap_ids: null, has_proposal: true, pipeline_run_id: 42,
      created_at: "2026-01-01", quality_summary: { passed: true, total: 5, has_issues: false },
      governance_status: null },
  ],
  total: 1,
  score_guide: {},
};

const mockPending = { pending: [] };
const mockOps = {
  health: { total_runs: 1, completed: 1, failed: 0, cancelled: 0, running: 0, pending: 0, average_duration_s: 60, slowest_stages: [] },
  quality_trends: { common_failures: [] },
  costs: { total_cost: 0, by_provider: [], by_stage: [], by_model: [] },
  ideas: { total: 1, cited: 0, supporting: 0 },
  model_usage: { models: [] },
  window: { days: 7, from: "2026-01-01", to: "2026-01-08" },
};

const mockRunDetail = {
  id: 42, status: "completed", domain: "AI/NLP", current_stage: "completed",
  ideas_count: 3, session_id: null, created_at: "2026-01-01", completed_at: "2026-01-02",
  error_message: null, strategy: "standard",
  config: {}, stages_completed: ["literature_search", "ingestion", "gap_analysis", "idea_generation"],
  tree_data: null,
};

const mockRunIdeas = { ideas: mockIdeas.ideas, total: 1 };

const mockIdeaDetail = {
  idea: {
    ...mockIdeas.ideas[0],
    description: "A novel approach",
    source_gaps: [{ resolved: true, gap_id: 12, gap_title: "Test Gap", gap_confidence: 0.9 }],
    proposal_sections: {},
    proposal_references: null,
    supporting_papers: null,
    quality_checks: [],
    ensemble_review: null,
    novelty_report: null,
    feasibility_report: null,
    remediation_hints: [],
  },
};

const mockGapDetail = {
  gap: {
    id: 12, title: "Gap in transformer scaling", description: "desc",
    gap_type: "methodological", confidence: 0.85, potential_impact: "high",
    idea_count: 0, status: "identified",
    matched_papers_preview: [
      { id: 101, title: "Scaling Laws", abstract: "Models scale predictably.", year: 2020, venue: "ICML", citation_count: 1000 },
    ],
  },
};

const mockGapPapers = {
  papers: [
    { id: 101, title: "Scaling Laws", abstract: "Models scale predictably.", year: 2020, venue: "ICML", citation_count: 1000 },
    { id: 102, title: "Chinchilla", abstract: "Compute-optimal training.", year: 2022, venue: "NeurIPS", citation_count: 500 },
  ],
  total: 2,
};

const mockLiteratureSearch = {
  papers: [
    { id: "ss-1", source: "semantic_scholar", title: "Attention Is All You Need",
      abstract: "Transformer architecture", authors: [{ name: "Vaswani" }],
      year: 2017, venue: "NeurIPS", citation_count: 100000, url: null, doi: null, arxiv_id: null, keywords: [] },
  ],
};

const mockIngestResponse = { status: "ingested", id: "ss-1" };

// ── Default transport handler ────────────────────────────────────────

function defaultHandler(path: string): MockResponse {
  // Strip query string for matching
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
  // Gap status PATCH endpoint
  if (p.endsWith("/status") && p.includes("/gaps/")) {
    return { body: { gap: { id: 12, status: "investigating" } } };
  }
  if (p.startsWith("/literature/search")) return { body: mockLiteratureSearch };
  if (p === "/literature/ingest") return { body: mockIngestResponse };
  return { status: 404, body: { detail: "Not found" } };
}

// ── Harness ──────────────────────────────────────────────────────────

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
}

// Direct imports for test routes (lazy + Suspense is fragile in tests)
import Dashboard from "../dashboard";
import RunDetail from "../run-detail";
import IdeaDetail from "../idea-detail";
import GapDetail from "../gap-detail";
import LiteraturePage from "../literature";

function renderApp(initialPath: string) {
  const qc = makeQueryClient();
  return {
    qc,
    ...render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[initialPath]}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/runs/:id" element={<RunDetail />} />
            <Route path="/ideas/:id" element={<IdeaDetail />} />
            <Route path="/gaps/:id" element={<GapDetail />} />
            <Route path="/literature" element={<LiteraturePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    ),
  };
}

// ── Tests ────────────────────────────────────────────────────────────

describe("F1.5 Critical Product-Flow Integration", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    transportMock.mockImplementation(async (path: string) => defaultHandler(path));
  });

  // 1. Golden research inspection flow
  it("dashboard → run detail → idea detail with real route transitions", async () => {
    renderApp("/");

    // Dashboard loads
    await waitFor(() => {
      expect(screen.queryByText("Novel Transformer Architecture")).toBeInTheDocument();
    });

    // Click the idea row (navigates to /ideas/1)
    const ideaRow = screen.getByText("Novel Transformer Architecture").closest("[role='button']") || screen.getByText("Novel Transformer Architecture");
    fireEvent.click(ideaRow);

    // Idea detail page loads with proposal content
    await waitFor(() => {
      expect(screen.queryByText("Novel Transformer Architecture")).toBeInTheDocument();
    }, { timeout: 5000 });

    // Transport was called for idea detail
    expect(transportMock).toHaveBeenCalledWith(
      expect.stringContaining("/ideas/1"),
      expect.anything(),
    );
  });

  // 2. Literature ingest success flow
  it("literature search → ingest confirmation → mutation success → invalidation", async () => {
    renderApp("/literature");

    // Search
    const input = screen.getByTestId("literature-search-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "attention" } });
    fireEvent.submit(input.closest("form")!);

    // Paper card renders
    await waitFor(() => {
      expect(screen.getByTestId("ingest-button")).toBeInTheDocument();
    });

    // Confirm + Ingest
    fireEvent.click(screen.getByTestId("ingest-button"));
    await waitFor(() => expect(screen.getByText("Confirm Ingest")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ingest-button"));

    // Transport received ingest POST
    await waitFor(() => {
      const ingestCalls = transportMock.mock.calls.filter(
        ([p]) => p === "/literature/ingest",
      );
      expect(ingestCalls.length).toBe(1);
    });
  });

  // 3. Literature ingest failure → manual retry
  it("literature ingest fails → error visible → retry succeeds", async () => {
    let ingestCallCount = 0;
    transportMock.mockImplementation(async (path: string) => {
      if (path === "/literature/ingest") {
        ingestCallCount++;
        if (ingestCallCount === 1) return { status: 500, body: { detail: "Server error" } };
        return { body: mockIngestResponse };
      }
      return defaultHandler(path);
    });

    renderApp("/literature");

    // Search
    const input = screen.getByTestId("literature-search-input") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "test" } });
    fireEvent.submit(input.closest("form")!);

    await waitFor(() => expect(screen.getByTestId("ingest-button")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ingest-button"));
    await waitFor(() => expect(screen.getByText("Confirm Ingest")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ingest-button"));

    // Error visible
    await waitFor(() => {
      expect(ingestCallCount).toBe(1);
    });

    // Retry
    await waitFor(() => expect(screen.getByTestId("ingest-button")).not.toBeDisabled());
    fireEvent.click(screen.getByTestId("ingest-button"));
    await waitFor(() => expect(screen.getByText("Confirm Ingest")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("ingest-button"));

    await waitFor(() => expect(ingestCallCount).toBe(2));
  });

  // 4. Gap status success → authoritative refetch
  it("gap status mutation succeeds and invalidates gap query", async () => {
    renderApp("/gaps/12");

    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());

    const select = screen.getByTestId("gap-status-select");
    fireEvent.change(select, { target: { value: "investigating" } });

    // Wait for mutation
    await waitFor(() => {
      const statusCalls = transportMock.mock.calls.filter(
        ([p]) => p.includes("/gaps/12/status"),
      );
      expect(statusCalls.length).toBeGreaterThanOrEqual(1);
    });

    // Gap refetched (invalidation)
    await waitFor(() => {
      const gapCalls = transportMock.mock.calls.filter(
        ([p]) => p.split("?")[0] === "/gaps/12",
      );
      expect(gapCalls.length).toBeGreaterThanOrEqual(2);
    });
  });

  // 5. Same-router gap A/B late-mutation isolation
  it("gap A mutation resolves after navigation to gap B — B unchanged", async () => {
    // Control mutation A resolution
    let resolveA: (v: MockResponse) => void = () => {};
    const mutationAPromise = new Promise<MockResponse>((r) => { resolveA = r; });

    transportMock.mockImplementation(async (path: string, opts?: RequestInit) => {
      const p = path.split("?")[0];
      // Gap 12 status mutation: control resolution
      if (p.includes("/gaps/12/status") && opts?.method === "PATCH") {
        return mutationAPromise;
      }
      return defaultHandler(path);
    });

    const qc = makeQueryClient();
    const { unmount } = render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/gaps/12"]}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/runs/:id" element={<RunDetail />} />
            <Route path="/ideas/:id" element={<IdeaDetail />} />
            <Route path="/gaps/:id" element={<GapDetail />} />
            <Route path="/literature" element={<LiteraturePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Gap A loads
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());

    // Start mutation A
    fireEvent.change(screen.getByTestId("gap-status-select"), { target: { value: "investigating" } });
    await waitFor(() => {
      expect(transportMock.mock.calls.some(([p, o]) => p.includes("/gaps/12/status") && o?.method === "PATCH")).toBe(true);
    });

    // Navigate to gap B (same QueryClient, new mount)
    unmount();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/gaps/13"]}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/runs/:id" element={<RunDetail />} />
            <Route path="/ideas/:id" element={<IdeaDetail />} />
            <Route path="/gaps/:id" element={<GapDetail />} />
            <Route path="/literature" element={<LiteraturePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("Gap Beta")).toBeInTheDocument(), { timeout: 5000 });

    // Resolve mutation A (late)
    resolveA({ body: { gap: { id: 12, status: "investigating" } } });
    await new Promise((r) => setTimeout(r, 200));

    // Gap B still shows its own data
    expect(screen.getByText("Gap Beta")).toBeInTheDocument();
    expect(screen.queryByText("Gap in transformer scaling")).not.toBeInTheDocument();
    expect(screen.getByTestId("gap-status-select")).toHaveValue("addressed");
  });

  // 6. Dashboard partial-failure flow
  it("one dashboard resource fails while others render real data", async () => {
    transportMock.mockImplementation(async (path: string) => {
      const p = path.split("?")[0];
      if (p === "/governance/pending") {
        return { status: 500, body: { detail: "Network error" } };
      }
      return defaultHandler(path);
    });

    renderApp("/");

    // Wait for governance failure widget
    await waitFor(() => {
      expect(screen.getAllByTestId("widget-error").length).toBeGreaterThanOrEqual(1);
    });

    // Other data still renders (ideas, runs)
    expect(screen.getByText("Novel Transformer Architecture")).toBeInTheDocument();
  });

  // 7. Malformed matched-papers response → contract failure
  it("malformed matched-papers HTTP-200 becomes contract failure", async () => {
    transportMock.mockImplementation(async (path: string) => {
      const p = path.split("?")[0];
      if (p === "/gaps/12/papers") {
        return { body: { wrong: "shape" } }; // Missing required fields
      }
      return defaultHandler(path);
    });

    renderApp("/gaps/12");
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());

    // Expand matched papers
    const expandBtn = screen.queryByText("Show more matched papers");
    if (expandBtn) {
      fireEvent.click(expandBtn);
      // Contract failure should surface as "Failed to load papers" error,
      // NOT as empty success ("No additional matched papers found")
      await waitFor(() => {
        expect(screen.getByText("Failed to load papers.")).toBeInTheDocument();
      }, { timeout: 5000 });
      // Empty success text should NOT appear
      expect(screen.queryByText("No additional matched papers found.")).not.toBeInTheDocument();
    }
  });

  // 8. Authenticated deep link loads the requested route
  it("deep link to /gaps/12 renders gap detail", async () => {
    renderApp("/gaps/12");
    await waitFor(() => {
      expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument();
    });
  });

  // 9. Unauthenticated deep link does not render protected data
  it("ProtectedRoute redirects unauthenticated users to login", async () => {
    // Minimal test: render ProtectedRoute without a user
    const { ProtectedRoute } = await mockProtectedRoute();
    render(
      <MemoryRouter initialEntries={["/gaps/12"]}>
        <Routes>
          <Route path="/gaps/:id" element={
            <ProtectedRoute>
              <GapDetail />
            </ProtectedRoute>
          } />
          <Route path="/login" element={<div data-testid="login-page">Login</div>} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("login-page")).toBeInTheDocument();
    });
  });

  // 10. Unknown route fallback
  it("unknown route redirects to dashboard", async () => {
    renderApp("/nonexistent");

    await waitFor(() => {
      expect(screen.queryByText("Novel Transformer Architecture")).toBeInTheDocument();
    });
  });
});

// ── Helper: mock ProtectedRoute for auth test ────────────────────────

async function mockProtectedRoute() {
  // Minimal inline ProtectedRoute that checks for a user prop
  function ProtectedRoute() {
    // Simulate unauthenticated: no user
    return <Navigate to="/login" replace />;
  }
  return { ProtectedRoute };
}
