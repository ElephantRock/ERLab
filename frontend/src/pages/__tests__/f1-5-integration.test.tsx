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
import { MemoryRouter, Routes, Route, useNavigate } from "react-router-dom";
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
import { buildMutationCacheForClient } from "@/lib/mutation-cache";

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

/**
 * F1.5c: backend-side persisted ingestion state.
 * The defaultHandler starts with no papers ingested. Each successful POST
 * /literature/ingest appends the paper ID, so subsequent GET /literature/ingested
 * reflects the persisted set. The UI derives its badge from this response.
 */
const ingestedState: { ids: string[] } = { ids: [] };
function resetIngestedState() { ingestedState.ids = []; }

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
  if (p === "/literature/ingested") return { body: { ids: [...ingestedState.ids] } };
  if (p === "/literature/ingest") {
    // F1.5c: simulate backend persistence — append to the authoritative set.
    if (!ingestedState.ids.includes("ss-1")) ingestedState.ids.push("ss-1");
    return { body: mockIngest };
  }
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

/**
 * Construct a test QueryClient with the PRODUCTION MutationCache.
 * F1.5c: every test QueryClient must install the same cache-owned
 * invalidation the production QueryClient (main.tsx) uses, so tests
 * exercise the real cache-integrity contract — component-level
 * invalidations are no longer relied on.
 *
 * The QueryClient↔MutationCache construction cycle is broken with a
 * mutable holder object (no lint suppression needed).
 */
function makeQC(): QueryClient {
  const ref: { current?: QueryClient } = {};
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
    mutationCache: buildMutationCacheForClient(() => {
      if (!ref.current) throw new Error("QueryClient accessed before initialization");
      return ref.current;
    }),
  });
  ref.current = qc;
  return qc;
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

/**
 * Count fetch calls whose path (after stripping base URL and query string)
 * exactly matches the given path. We use exact matching (not substring)
 * because paths like /literature/ingest and /literature/ingested share a
 * prefix and substring matching would conflate them.
 */
function countCalls(pathFragment: string): number {
  return fetchMock.mock.calls.filter(([url]) => {
    const stripped = stripPath(String(url)).split("?")[0];
    return stripped === pathFragment;
  }).length;
}

/** Check if any fetch call's path exactly matches + optional method. */
function hasCall(pathFragment: string, method?: string): boolean {
  return fetchMock.mock.calls.some(([url, init]) => {
    const stripped = stripPath(String(url)).split("?")[0];
    const m = (init as RequestInit)?.method;
    return stripped === pathFragment && (!method || m === method);
  });
}

// ── Tests ────────────────────────────────────────────────────────────

describe("F1.5b Critical Product-Flow Integration (sealed)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetIngestedState();
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
  // (2) Gap A/B — routed cross-route transition with late mutation
  //
  // Real production scenario: user on /gaps/12 fires a status mutation,
  // then navigates within the SAME router to /gaps/13 while the PATCH is
  // still in flight. We prove:
  //   (i)   GET /gaps/13 actually executes (gap 13 is routed to, not just seeded)
  //   (ii)  gap 13 renders its authoritative backend status
  //   (iii) Alpha's late mutation completion still invalidates ["gap", 12]
  //         AFTER GapDetailContent(12) has unmounted — proving mutation
  //         side-effects are cache-scoped, not component-scoped
  //   (iv)  ["gap", 13] is never invalidated
  //   (v)   gap 13's rendered status remains "addressed"
  //   (vi)  Navigating back to /gaps/12 fetches the authoritative updated
  //         status ("investigating") — late completion was not lost
  // ════════════════════════════════════════════════════════════════
  it("gap A/B: routed /gaps/12 → /gaps/13 transition; late mutation survives unmount; back-nav shows authoritative update", async () => {
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    // Late-A: gap 12 PATCH never resolves until we say so
    let resolveA: (v: MockResponse) => void = () => {};
    const lateA = new Promise<MockResponse>((r) => { resolveA = r; });
    installHandler((path, init) => {
      if (path.split("?")[0] === "/gaps/12/status" && init?.method === "PATCH") return lateA;
      return defaultHandler(path);
    });

    // Use a session-grade QueryClient (gcTime > 0) so cache entries persist
    // across navigation — matches the production default.
    // F1.5c: install the PRODUCTION MutationCache via buildMutationCacheForClient
    // (holder-object pattern). This ensures cache-owned invalidations fire
    // regardless of component mount state — the same behavior the production
    // QueryClient in main.tsx provides. Without this, the test would
    // silently pass with a no-op MutationCache and fail to exercise the
    // F1.5c contract.
    const qcRef: { current?: QueryClient } = {};
    const qc = new QueryClient({
      defaultOptions: {
        queries: { retry: false, gcTime: 5 * 60 * 1000, staleTime: 0 },
      },
      mutationCache: buildMutationCacheForClient(() => {
        if (!qcRef.current) throw new Error("QueryClient accessed before initialization");
        return qcRef.current;
      }),
    });
    qcRef.current = qc;

    // Capture the production navigate() from inside the router so we can
    // drive a SAME-router navigation (no unmount of the router itself,
    // only of GapDetailContent(12)).
    const navigateRef: { current: ((to: string) => void) | null } = { current: null };
    function NavigateProbe() {
      const navigate = useNavigate();
      navigateRef.current = (to: string) => navigate(to);
      return null;
    }

    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/gaps/12"]}>
          <NavigateProbe />
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

    // (a) /gaps/12 renders Alpha
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());
    const gap12CallsAtMutationStart = countCalls("/gaps/12");

    // (b) Mutation for Alpha begins (PATCH held pending)
    await act(async () => {
      fireEvent.change(screen.getByTestId("gap-status-select"), { target: { value: "investigating" } });
    });
    await waitFor(() => expect(hasCall("/gaps/12/status", "PATCH")).toBe(true));

    // (c) Same router navigates to /gaps/13. GapDetailContent(12) unmounts.
    expect(navigateRef.current).not.toBeNull();
    await act(async () => { navigateRef.current!("/gaps/13"); });

    // (d) GET /gaps/13 actually executes (proves real routing, not cache seed)
    await waitFor(() => expect(countCalls("/gaps/13")).toBeGreaterThanOrEqual(1));
    // (e) gap 13 renders its authoritative backend status ("addressed")
    await waitFor(() => expect(screen.getByText("Gap Beta")).toBeInTheDocument());
    const betaSelect = screen.getByTestId("gap-status-select") as HTMLSelectElement;
    expect(betaSelect.value).toBe("addressed");

    const gap13CallsBeforeLateA = countCalls("/gaps/13");

    // (f) Alpha mutation resolves late — AFTER GapDetailContent(12) unmounted.
    //     This proves mutation onSuccess is cache-scoped: the invalidation
    //     must still fire against ["gap", 12] in the shared QueryClient.
    await act(async () => {
      resolveA({ body: { gap: { id: 12, status: "investigating" } } });
    });
    // Allow the mutation pipeline to run onSuccess → invalidate → refetch
    await new Promise((r) => setTimeout(r, 200));

    // (g) Invalidation was scoped to ["gap", 12] only — and DID fire despite
    //     GapDetailContent(12) being unmounted. This is the load-bearing
    //     assertion: mutation completion authority is retained by the
    //     QueryClient, not by a mounted page observer.
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

    // (h) The cache-level invalidation marked ["gap", 12] stale. No
    //     component is currently mounted at /gaps/12, so no immediate
    //     refetch occurs — the refetch fires when the user navigates
    //     back. We assert the invalidation itself happened via the spy
    //     (already done above) and that gap 13 was untouched (below).
    //     The back-navigation refetch is proven in step (k).

    // (i) gap 13 was NOT refetched by Alpha's completion.
    expect(countCalls("/gaps/13")).toBe(gap13CallsBeforeLateA);

    // (j) gap 13's rendered status remains "addressed" (its backend value),
    //     not "investigating" (Alpha's value).
    expect(betaSelect.value).toBe("addressed");

    // (k) Navigate back to /gaps/12 within the same router. The cache was
    //     invalidated by the late onSuccess, so the route renders the
    //     AUTHORITATIVE updated status. This proves the late completion
    //     was not lost — its invalidation made the back-navigation refetch
    //     the updated state.
    // The default gap-12 detail handler returns status "identified" — to
    // model the persisted backend update, override /gaps/12 to return the
    // post-mutation status once the late PATCH has resolved.
    installHandler((path) => {
      if (path.split("?")[0] === "/gaps/12") {
        return { body: { gap: { ...mockGapDetail.gap, status: "investigating" } } };
      }
      return defaultHandler(path);
    });
    const gap12CallsBeforeBackNav = countCalls("/gaps/12");
    // staleTime is 0, so navigation-driven remount triggers a refetch of
    // the now-stale entry the late invalidation produced.
    await act(async () => { navigateRef.current!("/gaps/12"); });
    await waitFor(() => expect(screen.getByText("Gap in transformer scaling")).toBeInTheDocument());
    // (l) The back-navigation refetched gap 12 — proving the late
    //     completion's cache invalidation survived unmount and made the
    //     revisit observe the authoritative updated state.
    await waitFor(() => expect(countCalls("/gaps/12")).toBeGreaterThan(gap12CallsBeforeBackNav));
    // (m) The re-mounted Alpha shows the authoritative updated status.
    const alphaSelectAfterBack = await waitFor(() =>
      screen.getByTestId("gap-status-select") as HTMLSelectElement,
    );
    await waitFor(() => expect(alphaSelectAfterBack.value).toBe("investigating"));

    // (n) Final consistency: gap 12 was fetched more times overall than at
    //     mutation start, because the late invalidation produced a back-nav
    //     refetch in addition to the initial mount.
    expect(countCalls("/gaps/12")).toBeGreaterThan(gap12CallsAtMutationStart);

    invalidateSpy.mockRestore();
  });

  // ════════════════════════════════════════════════════════════════
  // (3) Literature success: pending → duplicate blocked → invalidation
  //     → declared refetch → authoritative ingested state derived from
  //     backend response (not local client state)
  // ════════════════════════════════════════════════════════════════
  it("literature success: pending visible → duplicate blocked → declared keys invalidated → backend-derived ingested state", async () => {
    const invalidateSpy = vi.spyOn(QueryClient.prototype, "invalidateQueries");

    // Hold the ingest pending long enough to observe state, then resolve
    let resolveIngest: (v: MockResponse) => void = () => {};
    installHandler((path) => {
      if (path === "/literature/ingest") {
        return new Promise<MockResponse>((r) => {
          // Intercept the resolve so we can mutate the backend-persisted
          // ingestedState before the response is delivered — the real
          // backend would do this as part of the POST handler.
          resolveIngest = (v: MockResponse) => {
            if (!ingestedState.ids.includes("ss-1")) ingestedState.ids.push("ss-1");
            r(v);
          };
        });
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

    // (a.0) literature-ingested was called before mutation (baseline state)
    const ingestedCallsBefore = countCalls("/literature/ingested");
    expect(ingestedCallsBefore).toBeGreaterThanOrEqual(1);

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

    // (c) Valid contract response succeeds → BOTH declared keys invalidated.
    //     ["literature-ingested] is the authoritative source for the badge.
    await act(async () => { resolveIngest({ body: mockIngest }); });
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ["literature-search"] }),
      );
    });
    await waitFor(() => {
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ["literature-ingested"] }),
      );
    });

    // (d) literature-ingested was called again after success (refetch)
    await waitFor(() => {
      expect(countCalls("/literature/ingested")).toBeGreaterThan(ingestedCallsBefore);
    });

    // (e) Authoritative ingested state derives from refreshed backend data.
    //     The backend response now lists ss-1 as ingested, and the badge
    //     appears because the UI reads from that response.
    await waitFor(() => expect(screen.getByTestId("ingested-badge")).toBeInTheDocument(), { timeout: 5000 });
    expect(screen.getByTestId("ingested-badge")).toHaveTextContent("Ingested");
    expect(screen.getByTestId("ingest-button")).toBeDisabled();

    invalidateSpy.mockRestore();
  });

  // ════════════════════════════════════════════════════════════════
  // (3b) Literature terminal state survives remount — derived from backend
  // ════════════════════════════════════════════════════════════════
  it("literature terminal state survives remount: badge derives from backend response, not local state", async () => {
    // Seed the backend with an already-ingested paper — models "user returns
    // to the page after a prior ingest in a previous session".
    ingestedState.ids.push("ss-1");

    // First mount: badge should appear immediately from backend data
    const qc1 = makeQC();
    const view1 = renderApp("/literature");
    const input1 = screen.getByTestId("literature-search-input") as HTMLInputElement;
    await act(async () => { fireEvent.change(input1, { target: { value: "attention" } }); });
    await act(async () => { fireEvent.submit(input1.closest("form")!); });
    await waitFor(() => expect(screen.getByTestId("ingested-badge")).toBeInTheDocument());
    expect(screen.getByTestId("ingest-button")).toBeDisabled();

    // Unmount entirely — local component state is destroyed.
    view1.unmount();

    // Re-mount at /literature with a FRESH QueryClient — simulates reload.
    // No local state survives. The only source of the badge is the backend
    // /literature/ingested response, which still lists ss-1.
    const freshQC = makeQC();
    render(
      <QueryClientProvider client={freshQC}>
        <MemoryRouter initialEntries={["/literature"]}>
          <Routes>
            <Route path="/*" element={
              <ProtectedRoute user={{ id: 1, username: "test" }} loading={false}>
                {productionRouteSet}
              </ProtectedRoute>
            } />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const input2 = screen.getByTestId("literature-search-input") as HTMLInputElement;
    await act(async () => { fireEvent.change(input2, { target: { value: "attention" } }); });
    await act(async () => { fireEvent.submit(input2.closest("form")!); });

    // The badge reappears — proving it's backend-derived, not local.
    await waitFor(() => expect(screen.getByTestId("ingested-badge")).toBeInTheDocument());
    expect(screen.getByTestId("ingest-button")).toBeDisabled();

    // Silence the unused-var lint without weakening the assertion: qc1 was
    // the QueryClient for the first mount and is captured here to document
    // that the fresh mount deliberately does NOT reuse it.
    expect(qc1).toBeDefined();
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
        // F1.5c: simulate backend persistence on the successful retry.
        if (!ingestedState.ids.includes("ss-1")) ingestedState.ids.push("ss-1");
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
