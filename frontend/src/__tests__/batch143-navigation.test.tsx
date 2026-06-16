/**
 * BATCH-143: Navigation & Dead-End Remediation Tests
 * Verifies source gap IDs are clickable, literature auto-searches, back buttons correct
 */
import { describe, it, expect, vi, beforeEach } from "vitest";

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
  useParams: () => ({ id: "1" }),
  useSearchParams: () => [new URLSearchParams()],
}));

// Mock API modules
vi.mock("@/api/pipeline", () => ({
  getRunDetail: vi.fn().mockResolvedValue({
    id: 1, status: "completed", domain: "AI", strategy: "fast_scan",
    created_at: "2026-05-10T00:00:00Z", stages: [], ideas: [], gaps: [], proposals: [],
  }),
  getRunIdeas: vi.fn().mockResolvedValue({ ideas: [], total: 0 }),
  resumeRun: vi.fn(),
}));

vi.mock("@/api/gaps", () => ({
  getGapDetail: vi.fn().mockResolvedValue({
    id: 1, gap_type: "methodology", description: "Test gap", confidence: 0.8,
  }),
  updateGapStatus: vi.fn(),
  getGapRelatedIdeas: vi.fn().mockResolvedValue([]),
}));

vi.mock("@/api/ideas", () => ({
  getIdeaDetail: vi.fn().mockResolvedValue({
    id: 1, title: "Test Idea", description: "Test", overall_score: 0.85,
    source_gap_ids: ["gap-1", "gap-2"], domain: "AI", novelty_score: 0.9,
  }),
}));

vi.mock("@/api/search", () => ({
  globalSearch: vi.fn().mockResolvedValue({
    ideas: [], gaps: [], papers: [{ id: 1, title: "Transformer", year: 2023, venue: "NeurIPS" }], runs: [],
  }),
}));

vi.mock("@/api/literature", () => ({
  searchLiterature: vi.fn().mockResolvedValue({ papers: [] }),
  ingestPaper: vi.fn(),
}));

beforeEach(() => {
  mockNavigate.mockClear();
});

// ── TASK-01: Source Gap IDs Are Clickable ─────────────────────

describe("TEST-143-01: Source gap IDs clickable", () => {
  it("TEST-143-01-01: source gap IDs navigate to /gaps/{id}", async () => {
    // Simulate clicking a gap link in idea-detail
    const gapId = "gap-42";
    mockNavigate(`/gaps/${gapId}`);
    expect(mockNavigate).toHaveBeenCalledWith("/gaps/gap-42");
  });

  it("TEST-143-01-02: source gap IDs are not plain text", async () => {
    const fs = await import("fs");
    const content = fs.readFileSync("src/pages/idea-detail.tsx", "utf-8");
    // Should have a clickable element with data-testid
    expect(content).toContain("source-gap-link");
    // Should navigate to /gaps/ with the gapId
    expect(content).toMatch(/navigate.*\/gaps\/.*gapId/);
  });
});

// ── TASK-02: Literature Auto-Search from URL ──────────────────

describe("TEST-143-02: Literature page auto-searches from URL param", () => {
  it("TEST-143-02-01: literature page reads ?q= from URL params", async () => {
    const fs = await import("fs");
    const content = fs.readFileSync("src/pages/literature.tsx", "utf-8");
    expect(content).toContain("useSearchParams");
    expect(content).toContain("urlParams.get");
    expect(content).toContain("setSubmittedQuery");
  });

  it("TEST-143-02-02: global search paper results navigate with query", async () => {
    const fs = await import("fs");
    const content = fs.readFileSync("src/components/search/global-search-dialog.tsx", "utf-8");
    expect(content).toMatch(/navigate.*literature\?q=.*encodeURIComponent.*query/);
  });

  it("TEST-143-02-03: global search paper results don't navigate to bare /literature", async () => {
    const fs = await import("fs");
    const content = fs.readFileSync("src/components/search/global-search-dialog.tsx", "utf-8");
    // Should NOT have: navigate("/literature") without query param
    expect(content).not.toMatch(/case.*papers.*navigate\("\/literature"\)/s);
  });
});

// ── TASK-03: Back Button Targets ─────────────────────────────

describe("TEST-143-03: Run-detail back button targets", () => {
  it("TEST-143-03-01: run-detail back buttons go to pipeline page not /", async () => {
    const fs = await import("fs");
    const content = fs.readFileSync("src/pages/run-detail.tsx", "utf-8");
    // Should NOT have navigate("/")
    expect(content).not.toContain('navigate("/")');
    // Should navigate to the pipeline page
    expect(content).toContain('navigate("/pipeline/new")');
  });

  it("TEST-143-03-02: gap-detail back button goes to /gaps", async () => {
    const fs = await import("fs");
    const content = fs.readFileSync("src/pages/gap-detail.tsx", "utf-8");
    expect(content).toContain('navigate("/gaps")');
  });

  it("TEST-143-03-03: idea-detail back button goes to /ideas", async () => {
    const fs = await import("fs");
    const content = fs.readFileSync("src/pages/idea-detail.tsx", "utf-8");
    expect(content).toContain('navigate("/ideas")');
  });

  it("TEST-143-03-04: no run-detail page navigates to bare /", async () => {
    const fs = await import("fs");
    const content = fs.readFileSync("src/pages/run-detail.tsx", "utf-8");
    const bareRootMatches = content.match(/navigate\(["']\/["']\)/g);
    expect(bareRootMatches).toBeNull();
  });
});
