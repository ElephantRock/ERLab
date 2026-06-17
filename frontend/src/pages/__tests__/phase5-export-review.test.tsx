/**
 * Phase 5: Export & Review Flows tests
 *
 * Covers:
 * - Run-level export buttons (Markdown, LaTeX, BibTeX) on completed runs
 * - Export buttons absent on running/failed runs
 * - apiFetchBlob download flow
 * - Governance error uses ErrorCard
 * - Governance empty state uses EmptyState
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import RunDetail from "@/pages/run-detail";
import GovernancePage from "@/pages/governance";

// ── Polyfills ──────────────────────────────────────────────────
class ResizeObserverMock { observe() {} unobserve() {} disconnect() {} }
global.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;

// ── Mocks ──────────────────────────────────────────────────────
vi.mock("@/api/pipeline", () => ({
  getRunDetail: vi.fn(),
  getRunIdeas: vi.fn(),
  resumeRun: vi.fn(),
}));

vi.mock("@/api/client", () => ({
  apiFetchBlob: vi.fn(),
  apiFetch: vi.fn(),
  getApiUrl: () => "",
  getApiKey: () => "",
  buildUrl: (p: string) => p,
  buildAuthHeaders: () => ({}),
}));

vi.mock("@/api/governance", () => ({
  getPending: vi.fn(),
  approveDecision: vi.fn(),
  denyDecision: vi.fn(),
}));

vi.mock("@/components/pipeline/tree-visualization", () => ({
  TreeVisualization: () => <div data-testid="tree-viz" />,
}));

vi.mock("@/components/ideas/idea-list-item", () => ({
  IdeaListItem: ({ idea }: { idea: { id: number; title: string } }) => (
    <div data-testid={`idea-${idea.id}`}>{idea.title}</div>
  ),
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

import { getRunDetail, getRunIdeas } from "@/api/pipeline";
import { apiFetchBlob } from "@/api/client";
import { getPending } from "@/api/governance";

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

function renderRunDetail(id: string) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[`/runs/${id}`]}>
        <Routes>
          <Route path="/runs/:id" element={<RunDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const completedRun = {
  id: 42,
  status: "completed",
  domain: "Machine Learning",
  current_stage: null,
  ideas_count: 3,
  session_id: "sess-1",
  created_at: "2026-06-15T10:00:00Z",
  completed_at: "2026-06-15T10:30:00Z",
  error_message: null,
  strategy: "deep_research",
  config: {},
  stages_completed: ["literature_search", "gap_analysis", "idea_generation", "evaluation", "synthesis"],
  ideas: [],
  tree_data: null,
};

const runningRun = {
  ...completedRun,
  status: "running",
  current_stage: "idea_generation",
  completed_at: null,
  stages_completed: ["literature_search", "gap_analysis"],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(getRunIdeas).mockResolvedValue({ ideas: [], total: 0 });
});

// ── Run-level export tests ─────────────────────────────────────

describe("Phase 5: Run-level export", () => {
  it("shows export buttons for completed runs", async () => {
    vi.mocked(getRunDetail).mockResolvedValue(completedRun);

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("run-export-section")).toBeInTheDocument();
    });
    expect(screen.getByTestId("export-markdown-btn")).toBeInTheDocument();
    expect(screen.getByTestId("export-latex-btn")).toBeInTheDocument();
    expect(screen.getByTestId("export-bibtex-btn")).toBeInTheDocument();
  });

  it("does not show export section for running runs", async () => {
    vi.mocked(getRunDetail).mockResolvedValue(runningRun);

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("run-detail")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("run-export-section")).not.toBeInTheDocument();
  });

  it("calls apiFetchBlob with correct path for markdown export", async () => {
    vi.mocked(getRunDetail).mockResolvedValue(completedRun);
    vi.mocked(apiFetchBlob).mockResolvedValue(new Blob(["test"], { type: "text/markdown" }));

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("export-markdown-btn")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("export-markdown-btn"));

    await waitFor(() => {
      expect(apiFetchBlob).toHaveBeenCalledWith("/export/markdown/42");
    });
  });

  it("calls apiFetchBlob with correct path for latex export", async () => {
    vi.mocked(getRunDetail).mockResolvedValue(completedRun);
    vi.mocked(apiFetchBlob).mockResolvedValue(new Blob(["test"], { type: "text/x-latex" }));

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("export-latex-btn")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("export-latex-btn"));

    await waitFor(() => {
      expect(apiFetchBlob).toHaveBeenCalledWith("/export/latex/42");
    });
  });

  it("calls apiFetchBlob with correct path for bibtex export", async () => {
    vi.mocked(getRunDetail).mockResolvedValue(completedRun);
    vi.mocked(apiFetchBlob).mockResolvedValue(new Blob(["test"], { type: "application/x-bibtex" }));

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("export-bibtex-btn")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("export-bibtex-btn"));

    await waitFor(() => {
      expect(apiFetchBlob).toHaveBeenCalledWith("/export/bibtex/42");
    });
  });

  it("shows toast error on export failure", async () => {
    const { toast } = await import("sonner");
    vi.mocked(getRunDetail).mockResolvedValue(completedRun);
    vi.mocked(apiFetchBlob).mockRejectedValue(new Error("Server error"));

    renderRunDetail("42");

    await waitFor(() => {
      expect(screen.getByTestId("export-markdown-btn")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId("export-markdown-btn"));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith("Export failed");
    });
  });
});

// ── Governance review flow tests ───────────────────────────────

describe("Phase 5: Governance review flows", () => {
  function renderGovernance() {
    return render(
      <MemoryRouter initialEntries={["/governance"]}>
        <Routes>
          <Route path="/governance" element={<GovernancePage />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  it("shows ErrorCard on API failure", async () => {
    vi.mocked(getPending).mockRejectedValue(new Error("Server unreachable"));

    renderGovernance();

    await waitFor(() => {
      expect(screen.getByTestId("governance-error")).toBeInTheDocument();
    });
    expect(screen.getByText("Failed to load pending approvals")).toBeInTheDocument();
  });

  it("shows EmptyState when no pending approvals", async () => {
    vi.mocked(getPending).mockResolvedValue({ pending: [] });

    renderGovernance();

    await waitFor(() => {
      expect(screen.getByTestId("governance-empty")).toBeInTheDocument();
    });
    expect(screen.getByText("No pending approvals")).toBeInTheDocument();
  });
});
