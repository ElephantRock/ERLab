import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";

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

// ── Mock API ─────────────────────────────────────────────────────
vi.mock("@/api/ideas", () => ({
  listIdeas: vi.fn(),
  getIdea: vi.fn(),
  refineIdea: vi.fn(),
}));

vi.mock("@/components/ideas/score-badge", () => ({
  ScoreBadge: ({ score }: { score: number }) => (
    <span data-testid="score-badge">{score}</span>
  ),
}));

vi.mock("@/components/ideas/export-button", () => ({
  ExportButton: () => <button data-testid="export-btn">Export</button>,
}));

vi.mock("@/components/export/export-dialog", () => ({
  ExportDialog: ({ ideaId, ideaIds }: { ideaId?: number; ideaIds?: number[] }) => (
    <div data-testid="export-dialog" data-idea-id={ideaId} data-idea-ids={ideaIds?.join(",")}>
      Export {ideaId ? `Idea ${ideaId}` : `${ideaIds?.length} Ideas`}
    </div>
  ),
}));

vi.mock("@/components/ideas/idea-card", () => ({
  IdeaCard: ({ idea, onClick }: { idea: any; onClick?: () => void }) => (
    <div data-testid={`idea-card-${idea.id}`} onClick={onClick}>
      {idea.title}
    </div>
  ),
}));

vi.mock("@/components/ideas/feedback-form", () => ({
  FeedbackForm: ({ ideaId }: { ideaId: number }) => (
    <div data-testid="feedback-form">Feedback for {ideaId}</div>
  ),
}));

vi.mock("@/components/ideas/novelty-report-view", () => ({
  NoveltyReportView: () => <div data-testid="novelty-report" />,
}));

vi.mock("@/components/ideas/feasibility-report-view", () => ({
  FeasibilityReportView: () => <div data-testid="feasibility-report" />,
}));

vi.mock("@/components/markdown/markdown-renderer", () => ({
  MarkdownRenderer: ({ content }: { content: string }) => (
    <div data-testid="markdown">{content}</div>
  ),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { getIdea, listIdeas } from "@/api/ideas";
import IdeaDetail from "@/pages/idea-detail";
import IdeasBrowser from "@/pages/ideas-browser";

const mockedGetIdea = vi.mocked(getIdea);
const mockedListIdeas = vi.mocked(listIdeas);

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ── TEST-33-03-01: Idea detail has export button ──────────────────

describe("IdeaDetail — Export Button (BATCH-33)", () => {
  it("TEST-33-03-01: idea detail has export button with PDF export", async () => {
    const sampleIdea = {
      id: 1,
      title: "Quantum NLP",
      domain: "AI/NLP",
      novelty_score: 0.92,
      feasibility_score: 4.5,
      overall_score: 0.68,
      pipeline_run_id: null,
      created_at: "2026-05-01T00:00:00Z",
      problem_statement: "Low-resource languages.",
      proposed_method: "Quantum embeddings.",
      expected_contributions: "Novel hybrid approach.",
      novelty_report: null,
      feasibility_report: null,
      proposal_md: "# Proposal",
      proposal_latex: null,
      proposal_sections: null,
    };
    mockedGetIdea.mockResolvedValue({ idea: sampleIdea });

    const qc = createQueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={["/ideas/1"]}>
          <Routes>
            <Route path="/ideas/:id" element={<IdeaDetail />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Quantum NLP")).toBeInTheDocument();
    });

    // Export dialog should be present
    const exportEl = screen.getByTestId("export-dialog");
    expect(exportEl).toBeInTheDocument();
    expect(exportEl.getAttribute("data-idea-id")).toBe("1");
  });
});

// ── TEST-33-03-02: Bulk export removed from ideas browser (Phase 3 rebuild) ──
// The old ideas-browser had multi-select checkboxes and a bulk-export dialog.
// The Phase 3 rebuild simplified the browser to a triage surface with direct
// navigation. Bulk export is available from individual idea-detail pages and
// the /export/bulk API endpoint. This test documents the change.

describe("IdeasBrowser — no bulk export (Phase 3 simplification)", () => {
  it("renders triage cards without multi-select checkboxes", async () => {
    mockedListIdeas.mockResolvedValue({
      ideas: [
        { id: 1, title: "Idea 1", domain: "AI", novelty_score: 0.5, feasibility_score: 5, overall_score: 0.5, source_gap_ids: null, has_proposal: true, pipeline_run_id: null, created_at: "2026-05-01" },
        { id: 2, title: "Idea 2", domain: "ML", novelty_score: 0.7, feasibility_score: 7, overall_score: 0.7, source_gap_ids: null, has_proposal: false, pipeline_run_id: null, created_at: "2026-05-01" },
      ],
      total: 2,
      score_guide: {},
    });

    const qc = createQueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <IdeasBrowser />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // Cards render with direct navigation (no select wrapper)
    await waitFor(() => {
      expect(screen.getByText("Idea 1")).toBeInTheDocument();
    });

    // The old multi-select UI is gone
    expect(screen.queryByTestId("select-idea-1")).not.toBeInTheDocument();
  });
});
