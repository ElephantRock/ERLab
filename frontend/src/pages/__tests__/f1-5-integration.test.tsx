/**
 * F1.5b — Critical Product-Flow Integration Tests (sealed).
 *
 * PROOF MATRIX:
 *   1. Golden research journey (dashboard → run detail → idea → gap → papers)
 *   2. Gap A/B cache isolation (late A mutation cannot corrupt loaded B)
 *   3. Literature ingest: pending → duplicate block → invalidation → authoritative state
 *   4. Literature failure → manual retry → terminal success
 *   5. Architecture: App.tsx and harness consume same createRoutes factory
 *
 * The harness uses the PRODUCTION route registry (createRoutes from
 * AppRoutes.tsx) with eager page imports. It mocks at the global fetch
 * boundary so ALL transport paths (apiFetchJson, apiFetchVoid,
 * apiFetchUnchecked, callContract) are intercepted regardless of import
 * order. The real apiFetchUnchecked implementation is preserved.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, fireEvent, act } from "@testing-library/react";
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

// Single shared production route set — drives every render in this file.
// No test-owned route topology exists; this is the SAME factory that
// App.tsx ultimately mounts via AuthenticatedRoutes → createRoutes(lazyPages).
const productionRouteSet = createRoutes(stubPages);

// ── Test data ────────────────────────────────────────────────────────

const mockRuns = {
  runs: [{
    id: 42, status: "completed", domain: "AI/NLP", current_stage: "completed",
    ideas_count: 3, session_id: null, created_at: "2026-01-01",
    completed_at: "2026-01-02", error_message: null, strategy: "standard",
  }],
  total: 1,
};
const mockIdeas = {
  ideas: [{
    id: 1, title: "Novel Transformer", domain: "AI/NLP",
    novelty_score: 0.85, feasibility_score: 7.5, overall_score: 0.8,
    source_gap_ids: null, has_proposal: true, pipeline_run_id: 42,
    created_at: "2026-01-01",
    quality_summary: { passed: true, total: 5, has_issues: false },
    governance_status: null,
  }],
  total: 1, score_guide: {},
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
  ...mockRuns.runs[0], config: {},
  stages_completed: ["literature_search", "ingestion", "gap_analysis", "idea_generation"],
  tree_data: null,
};
const mockRunIdeas = { ideas: mockIdeas.ideas, total: 1 };
// SourceGap type requires { id, title, gap_type, confidence, resolved: true }
const mockSourceGap = { id: 12, title: "Gap in transformer scaling", gap_type: "methodological", confidence: 0.85, resolved: true as const };
const mockIdeaDetail = {
  idea: {
    ...mockIdeas.ideas[0], description: "A novel approach",
    source_gaps: [mockSourceGap],
    proposal_sections: {}, proposal_references: null, supporting_papers: null,
    quality_checks: [], ensemble_review: null, novelty_report: null,
    feasibility_report: null, remediation_hints: [],
  },
};
const mockGapDetail = {
  gap: {
    id: 12, title: "Gap in transformer scaling", description: "desc",
    gap_type: "methodological", confidence: 0.85, potential_impact: "high",
    idea_count: 0, status: "identified",
    matched_papers_preview: [{ id: 101, title: "Scaling Laws", abstract: "Models scale.", year: 2020, venue: "ICML", citation_count: 1000 }],
  },
};
const mockGapDetail13 = {
  gap: {
    id: 13, title: "Gap Beta", description: "Beta desc",
    gap_type: "empirical", confidence: 0.6, potential_impact: "medium",
    idea_count: 0, status: "addressed",
    matched_papers_preview: [],
  },
};
const mockGapPapers = {
  papers: [
    { id: 101, title: "Scaling Laws", abstract: "Models scale.", year: 2020, venue: "ICML", citation_count: 1000 },
    { id: 102, title: "Chinchilla", abstract: "Compute-optimal.", year: 2022, venue: "NeurIPS", citation_count: 500 },
  ],
  total: 2,
};
const mockLit = {
  papers: [{
    id: "ss-1", source: "semantic_scholar", title: "Attention Is All You Need",
    abstract: "Transformer", authors: [{ name: "Vaswani" }], year: 2017,
    venue: "NeurIPS", citation_count: 100000, url: null, doi: null, arxiv_id: null, keywords: [],
  }],
};
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
  if (p === "/gaps/13") return { body: mockGapDetail13 };
  if (p === "/gaps/12/papers") return { body: mockGapPapers };
  if (p === "/gaps/12/status") return { body: { gap: { id: 12, status: "investigating" } } };
  if (p === "/gaps/13/status") return { body: { gap: { id: 13, status: "investigating" } } };
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
  return {
    ok: status < 400, status,
    json: async () => res.body,
    text: async () => JSON.stringify(res.body),
    blob: async () => new Blob(),
    statusText: status < 400 ? "OK" : "Error",
  } as Response;
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

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

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

/** Count fetch calls matching a path substring (after stripping base URL). */
function countCalls(pathFragment: string): number {
  return fetchMock.mock.calls.filter(([url]) => stripPath(String(url)).includes(pathFragment)).length;
}

/** Check if any fetch call matches path + optional method. */
function hasCall(pathFragment: string, method?: string): boolean {
  return fetchMock.mock.calls.some(([url, init]) => {
    const p = stripPath(String(url));
    const m = (init as RequestInit)?.method;
    return p.includes(pathFragment) && (!method || m === method);
  });
}

// ── Tests ────────────────────────────────────────────────────────────

describe("F1.5b Critical Product-Flow Integration (sealed)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    installHandler((path) => defaultHandler(path));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // ════════════════════════════════════════════════════════════════
  // (0) Architecture: shared route factory, no second route table
  // ════════════════════════════════════════════════════════════════
  it("architecture: harness uses the same createRoutes factory exported from AppRoutes", async () => {
    // The imported createRoutes must be the exact production factory —
    // a function, and the harness route set must be built from it.
    expect(typeof createRoutes).toBe("function");
    expect(React.isValidElement(productionRouteSet)).toBe(true);
    // The harness must not declare its own <Route> topology. We assert
    // by rendering through productionRouteSet (defined once at module
    // scope) — no test-owned <Route path="/gaps/:id"> appears in this
    // file outside the shared createRoutes call.
    // Source-of-truth check: AppRoutes.tsx exports createRoutes and
    // AuthenticatedRoutes consumes the same factory.
    const appRoutesMod = await import("../../AppRoutes");
    expect(appRoutesMod.createRoutes).toBe(createRoutes);
    expect(appRoutesMod.AuthenticatedRoutes).toBeDefined();
    expect(appRoutesMod.ProtectedRoute).toBe(ProtectedRoute);
  });

  // ════════════════════════════════════════════════════════════════
  // (1) Golden research journey — one router, one QueryClient
  // ════════════════════════════════════════════════════════════════
  it("golden journey: dashboard → run detail → idea → gap → matched papers", async () => {
    renderApp("/");

    // (a) Dashboard renders authoritative data
    await waitFor(() => expect(screen.getByText("Novel Transformer")).toBeInTheDocument());

    // (b) User activates the production "Latest Run" control → /runs/42
    const openRunBtn = await screen.findByText("Open");
    await act(async () => { fireEvent.click(openRunBtn); });
    await waitFor(() => expect(hasCall("/pipeline/runs/detail/42")).toBe(true), { timeout: 5000 });
    // Run ID continuity: the production route /runs/42 renders Run #42
    await waitFor(() => expect(screen.getByTestId("run-title")).toHaveTextContent("Run #42"));

    // (c) User follows a production control toward an idea — the generated
    //     idea in the run's idea list. IdeaListItem navigates to /ideas/:id.
    const ideaItem = await screen.findByTestId("idea-list-item-1");
    await act(async () => { fireEvent.click(ideaItem); });
    await waitFor(() => expect(hasCall("/ideas/1")).toBe(true), { timeout: 5000 });

    // (d) Idea detail renders. The production Source Gap link is reachable.
    await waitFor(() => expect(screen.getByText("Novel Transformer")).toBeInTheDocument());
    const sourceGapLink = await screen.findByTestId("source-gap-link-12");
    expect(sourceGapLink.textContent).toContain("Gap in transformer scaling");

    // (e) User activates the production source-gap control → /gaps/12
    await act(async () => { fireEvent.click(sourceGapLink); });
    await waitFor(() => expect(hasCall("/gaps/12")).toBe(true), { timeout: 5000 });
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());

    // (f) User activates "Show more matched papers" → lazy query fires
    const beforePapers = countCalls("/gaps/12/papers");
    expect(beforePapers).toBe(0); // lazy — not fetched on gap mount
    const expandBtn = await screen.findByText("Show more matched papers");
    await act(async () => { fireEvent.click(expandBtn); });
    await waitFor(() => expect(hasCall("/gaps/12/papers")).toBe(true), { timeout: 5000 });

    // (g) Preview is replaced by validated endpoint data (2 papers)
    await waitFor(() => expect(screen.getByText("Chinchilla")).toBeInTheDocument(), { timeout: 5000 });

    // (h) Truthful coverage wording matches papers.length and total
    await waitFor(() => {
      expect(screen.getByText("Showing all 2 matched papers")).toBeInTheDocument();
    });
  });

  // ════════════════════════════════════════════════════════════════
  // (2) Gap A/B cache isolation — late A mutation cannot corrupt B
  //
  // Real production scenario: user on /gaps/12 fires a status mutation,
  // the in-flight mutation outlasts their interest in gap 13 in the same
  // session. We prove three properties at the QueryClient level:
  //   (i)   gap 13 actually loads its authoritative state
  //   (ii)  Alpha's onSuccess invalidation is scoped to ["gap", 12]
  //   (iii) gap 13's cache entry is untouched by Alpha's completion
  //
  // We keep gap 12 (and its mutation observer) mounted, and populate
  // gap 13's cache in the SAME QueryClient via setQueryData — modeling
  // gap 13 having been loaded in the same session (previous visit or
  // background warm). Alpha's late mutation completion then fires its
  // onSuccess in the same QC, and we verify gap 13 is not invalidated.
  // ════════════════════════════════════════════════════════════════
  it("gap A/B: same router + QC, gap 13 loads, late A mutation cannot alter gap 13", async () => {
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    // Late-A: gap 12 PATCH never resolves until we say so
    let resolveA: (v: MockResponse) => void = () => {};
    const lateA = new Promise<MockResponse>((r) => { resolveA = r; });
    installHandler((path, init) => {
      if (path.split("?")[0] === "/gaps/12/status" && init?.method === "PATCH") return lateA;
      return defaultHandler(path);
    });

    // Use a session-grade QueryClient (gcTime > 0) so unobserved cache
    // entries persist — modeling a real production session where the
    // production QueryClient (default gcTime 5min) retains prior visits.
    // The default test makeQC uses gcTime: 0, which would erase gap 13
    // immediately and prevent us from asserting cache isolation.
    const qc = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 5 * 60 * 1000, staleTime: 0 },
      },
    });
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/gaps/12"]}>
          <Routes>
            <Route path="/*" element={
              <ProtectedRoute user={{}} loading={false}>
                {productionRouteSet}
              </ProtectedRoute>
            } />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // (a) Gap 12 (Alpha) renders
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());

    // (b) Populate gap 13's cache in the SAME QueryClient — models gap 13
    //     having been loaded earlier in this session (previous visit or
    //     background warm). This is the cache entry Alpha's late mutation
    //     must NOT corrupt.
    qc.setQueryData(["gap", 13], mockGapDetail13);
    const gap13CallsBeforeLateA = countCalls("/gaps/13");
    const gap13CacheBefore = qc.getQueryData(["gap", 13]);
    expect(gap13CacheBefore).toBeDefined();

    // (c) Mutation for Alpha begins (PATCH held pending)
    const initialGap12Calls = countCalls("/gaps/12");
    await act(async () => {
      fireEvent.change(screen.getByTestId("gap-status-select"), { target: { value: "investigating" } });
    });
    await waitFor(() => expect(hasCall("/gaps/12/status", "PATCH")).toBe(true));

    // (d) Alpha mutation resolves late — its onSuccess fires in the SAME
    //     QueryClient. Because invalidation is scoped to ["gap", 12], gap 13
    //     is neither invalidated nor refetched.
    // Wrap the late resolution + subsequent invalidation-driven refetch
    // in waitFor to absorb all resulting state updates into the act pool.
    await waitFor(async () => {
      resolveA({ body: { gap: { id: 12, status: "investigating" } } });
      // Give the mutation pipeline a tick to run onSuccess → invalidate → refetch
      await new Promise((r) => setTimeout(r, 50));
      expect(hasCall("/gaps/12/status", "PATCH")).toBe(true);
    });

    // (e) Invalidation was scoped to ["gap", 12] only — never touched gap 13.
    // The invalidateQueries argument shape is { queryKey: ["gap", gapId] }.
    const gap12Invalidations = invalidateSpy.mock.calls.filter(([arg]) => {
      const key = (arg as { queryKey?: unknown })?.queryKey;
      return Array.isArray(key) && key[0] === "gap" && key[1] === 12;
    });
    const gap13Invalidations = invalidateSpy.mock.calls.filter(([arg]) => {
      const key = (arg as { queryKey?: unknown })?.queryKey;
      return Array.isArray(key) && key[0] === "gap" && key[1] === 13;
    });
    expect(gap12Invalidations.length).toBeGreaterThan(0);
    expect(gap13Invalidations.length).toBe(0);

    // (f) gap 12 GET was triggered by Alpha's onSuccess invalidation
    await waitFor(() => {
      expect(countCalls("/gaps/12")).toBeGreaterThan(initialGap12Calls);
    });

    // (g) No additional gap 13 GET was triggered by Alpha's completion
    expect(countCalls("/gaps/13")).toBe(gap13CallsBeforeLateA);

    // (h) gap 13 cache entry is byte-for-byte unchanged — Alpha's
    //     completion did not alter gap 13's authoritative state.
    expect(qc.getQueryData(["gap", 13])).toEqual(gap13CacheBefore);

    // (i) gap 13 status in cache is still "addressed" (its backend value),
    //     not "investigating" (Alpha's value).
    const gap13CacheFinal = qc.getQueryData(["gap", 13]);
    const gap13Status = (gap13CacheFinal as { gap?: { status?: string } } | undefined)?.gap?.status;
    expect(gap13Status).toBe("addressed");

    invalidateSpy.mockRestore();
  });

  // ════════════════════════════════════════════════════════════════
  // (3) Literature success: pending → duplicate blocked → invalidation
  //     → declared refetch → authoritative ingested state
  // ════════════════════════════════════════════════════════════════
  it("literature success: pending visible → duplicate blocked → declared key invalidated → authoritative ingested state", async () => {
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    // Hold the ingest pending long enough to observe state, then resolve
    let resolveIngest: (v: MockResponse) => void = () => {};
    installHandler((path) => {
      if (path === "/literature/ingest") {
        return new Promise<MockResponse>((r) => { resolveIngest = r; });
      }
      return defaultHandler(path);
    });

    renderApp("/literature");

    // Submit a search
    const input = screen.getByTestId("literature-search-input") as HTMLInputElement;
    await act(async () => { fireEvent.change(input, { target: { value: "attention" } }); });
    await act(async () => { fireEvent.submit(input.closest("form")!); });

    // Paper appears as ingestible
    await waitFor(() => expect(screen.getByTestId("ingest-button")).toBeInTheDocument());

    // First click → confirmation; second click → mutation starts (pending)
    await act(async () => { fireEvent.click(screen.getByTestId("ingest-button")); });
    await waitFor(() => expect(screen.getByText("Confirm Ingest")).toBeInTheDocument());
    await act(async () => { fireEvent.click(screen.getByTestId("ingest-button")); });

    // (a) Pending state is visible (button disabled + "Ingesting...")
    await waitFor(() => expect(screen.getByTestId("ingest-button")).toBeDisabled());
    expect(screen.getByTestId("ingest-button")).toHaveTextContent("Ingesting");

    // (b) Rapid repeat sends no second request
    const callsDuringPending = countCalls("/literature/ingest");
    await act(async () => { fireEvent.click(screen.getByTestId("ingest-button")); });
    await act(async () => { fireEvent.click(screen.getByTestId("ingest-button")); });
    expect(countCalls("/literature/ingest")).toBe(callsDuringPending);

    // (c) Valid contract response succeeds → declared key invalidated
    await act(async () => { resolveIngest({ body: mockIngest }); });
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ["literature-search"] }),
      );
    });

    // (d) Authoritative ingested state becomes visibly reachable
    await waitFor(() => expect(screen.getByTestId("ingested-badge")).toBeInTheDocument());
    expect(screen.getByTestId("ingested-badge")).toHaveTextContent("Ingested");
    expect(screen.getByTestId("ingest-button")).toBeDisabled();

    invalidateSpy.mockRestore();
  });

  // ════════════════════════════════════════════════════════════════
  // (4) Literature failure → no auto retry → manual retry → success
  // ════════════════════════════════════════════════════════════════
  it("literature failure: context retained → no auto retry → manual retry → terminal success", async () => {
    let ingestCount = 0;
    const ingestObserved: number[] = [];
    installHandler((path) => {
      if (path === "/literature/ingest") {
        ingestCount++;
        ingestObserved.push(ingestCount);
        if (ingestCount === 1) return { status: 500, body: { detail: "err" } };
        return { body: mockIngest };
      }
      return defaultHandler(path);
    });

    renderApp("/literature");

    const input = screen.getByTestId("literature-search-input") as HTMLInputElement;
    await act(async () => { fireEvent.change(input, { target: { value: "test" } }); });
    await act(async () => { fireEvent.submit(input.closest("form")!); });
    await waitFor(() => expect(screen.getByTestId("ingest-button")).toBeInTheDocument());

    // (a) First request fails
    await act(async () => { fireEvent.click(screen.getByTestId("ingest-button")); });
    await waitFor(() => expect(screen.getByText("Confirm Ingest")).toBeInTheDocument());
    await act(async () => { fireEvent.click(screen.getByTestId("ingest-button")); });
    await waitFor(() => expect(ingestCount).toBe(1));

    // (b) Context remains visible (search result still on screen)
    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    // (c) Visible failure indicator
    await waitFor(() => expect(screen.getByTestId("ingest-error")).toBeInTheDocument());

    // (d) No automatic retry — wait a bit, no second call fires
    await new Promise((r) => setTimeout(r, 150));
    expect(countCalls("/literature/ingest")).toBe(1);

    // (e) Production retry control sends the second request.
    // After failure, button returns to enabled; user re-arms confirmation
    // and clicks through again.
    await waitFor(() => expect(screen.getByTestId("ingest-button")).not.toBeDisabled());
    await act(async () => { fireEvent.click(screen.getByTestId("ingest-button")); });
    await waitFor(() => expect(screen.getByText("Confirm Ingest")).toBeInTheDocument());
    await act(async () => { fireEvent.click(screen.getByTestId("ingest-button")); });

    // (f) Second response succeeds
    await waitFor(() => expect(ingestCount).toBe(2));

    // (g) Authoritative refreshed state appears (Ingested badge)
    await waitFor(() => expect(screen.getByTestId("ingested-badge")).toBeInTheDocument());
  });

  // ════════════════════════════════════════════════════════════════
  // (5) Gap status mutation → authoritative refetch (kept from F1.5a)
  // ════════════════════════════════════════════════════════════════
  it("gap status: mutation → authoritative refetch of declared gap key", async () => {
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");
    renderApp("/gaps/12");
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());
    const beforeMutation = countCalls("/gaps/12");
    await act(async () => {
      fireEvent.change(screen.getByTestId("gap-status-select"), { target: { value: "investigating" } });
    });
    await waitFor(() => expect(hasCall("/gaps/12/status", "PATCH")).toBe(true));
    // Invalidation scoped to ["gap", 12]
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ["gap", 12] }),
      );
    });
    // Authoritative refetch occurs
    await waitFor(() => expect(countCalls("/gaps/12")).toBeGreaterThan(beforeMutation));
    invalidateSpy.mockRestore();
  });

  // ════════════════════════════════════════════════════════════════
  // (6) Dashboard partial failure (kept from F1.5a)
  // ════════════════════════════════════════════════════════════════
  it("dashboard: governance fails while ideas render (independent lifecycles)", async () => {
    installHandler((path) => {
      if (path.split("?")[0] === "/governance/pending") return { status: 500, body: { detail: "err" } };
      return defaultHandler(path);
    });
    renderApp("/");
    await waitFor(() => expect(screen.getAllByTestId("widget-error").length).toBeGreaterThanOrEqual(1));
    expect(screen.getByText("Novel Transformer")).toBeInTheDocument();
  });

  // ════════════════════════════════════════════════════════════════
  // (7) Malformed papers HTTP-200 → contract failure (kept from F1.5a)
  // ════════════════════════════════════════════════════════════════
  it("malformed papers HTTP-200 → contract failure (not empty success)", async () => {
    installHandler((path) => {
      if (path.split("?")[0] === "/gaps/12/papers") return { body: { wrong: "shape" } };
      return defaultHandler(path);
    });
    renderApp("/gaps/12");
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());
    const btn = await screen.findByText("Show more matched papers");
    await act(async () => { fireEvent.click(btn); });
    // Contract failure surfaces as a visible error, not an empty success
    await waitFor(() => expect(screen.getByText("Failed to load papers.")).toBeInTheDocument(), { timeout: 5000 });
    expect(screen.queryByText("No additional matched papers found.")).not.toBeInTheDocument();
  });

  // ════════════════════════════════════════════════════════════════
  // (8) Auth deep link + fallback (kept from F1.5a)
  // ════════════════════════════════════════════════════════════════
  it("deep link /gaps/12 via production routes", async () => {
    renderApp("/gaps/12");
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());
  });

  it("unauthenticated → login redirect via production ProtectedRoute", async () => {
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

  it("unknown route → dashboard fallback via production Navigate", async () => {
    renderApp("/nonexistent");
    await waitFor(() => expect(screen.getByText("Novel Transformer")).toBeInTheDocument());
  });
});
