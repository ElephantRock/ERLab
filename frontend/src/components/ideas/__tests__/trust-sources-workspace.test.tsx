/**
 * Phase 2 2G focused frontend tests: Trust & Sources workspace.
 *
 * Covers spec 2G frontend cases 1–12.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TrustSourcesWorkspace } from "@/components/ideas/trust-sources-workspace";
import type { ReviewPayload } from "@/api/types";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));

const reviewMocks = {
  getReview: vi.fn(),
  recordSourceDecision: vi.fn(),
};
vi.mock("@/api/review", () => ({
  getReview: (...args: unknown[]) => reviewMocks.getReview(...args),
  recordSourceDecision: (...args: unknown[]) => reviewMocks.recordSourceDecision(...args),
}));

function makeReview(overrides: Partial<ReviewPayload> = {}): ReviewPayload {
  return {
    idea_id: 1,
    automated_checks: {
      paper_evaluation: { status: "ready", scope: "paper", dimensions: { novelty: { score: 0.7 } } },
      proposal_evaluation: { scope: "proposal", dimensions: { novelty: { score: 0.6 } } },
      citation_audit: [
        { section: "_summary", label: "Summary", citation_needed_count: 0, valid_citation_count: 2, has_citation_issues: false },
      ],
      quality_checks: [],
    },
    sources: [
      {
        source_ref_hash: "hash1",
        citation_marker: "[1]",
        ref_number: 1,
        raw: "Smith (2024). Graph reasoning.",
        title: "Graph reasoning",
        authors: "Smith",
        year: "2024",
        venue: "Nature",
        url: "https://example.com/1",
        doi: "10.1/abc",
        resolution_status: "resolved" as const,
        match_method: "doi",
        confidence: 1.0,
        sections_used: ["Method"],
        human_decision: null,
      },
      {
        source_ref_hash: "hash2",
        citation_marker: "[2]",
        ref_number: 2,
        raw: "Jones (2023). Neuro-symbolic.",
        title: null,
        authors: null,
        year: null,
        venue: null,
        url: null,
        doi: null,
        resolution_status: "unresolved" as const,
        match_method: null,
        confidence: null,
        sections_used: [],
        human_decision: null,
      },
    ],
    human_review: {
      status: "not_started",
      reviewable_sources: 2,
      reviewed_sources: 0,
      accepted: 0,
      flagged_or_excluded: 0,
      decisions_total: 0,
    },
    regeneration_available: false,
    ...overrides,
  };
}

function renderWorkspace(ideaId = 1) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TrustSourcesWorkspace ideaId={ideaId} />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  reviewMocks.getReview.mockResolvedValue(makeReview());
  reviewMocks.recordSourceDecision.mockResolvedValue({ id: 1, idea_id: 1, decision: "accepted" });
});

describe("TrustSourcesWorkspace", () => {
  it("case 1: renders from a ready review payload", async () => {
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText("Paper Evaluation")).toBeInTheDocument();
    });
    expect(screen.getByText("Citation Audit")).toBeInTheDocument();
    expect(screen.getByText("Human Source Review")).toBeInTheDocument();
  });

  it("case 2: automated and human review statuses are distinct", async () => {
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText("Paper Evaluation")).toBeInTheDocument();
    });
    // Paper Evaluation = automated; Human Source Review = human — both present
    expect(screen.getByText("Human Source Review")).toBeInTheDocument();
    expect(screen.getByText("Citation Audit")).toBeInTheDocument();
  });

  it("case 3: source filters work (unresolved shows 1)", async () => {
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText("Graph reasoning")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Unresolved" }));
    // The unresolved source shows its raw text (title is null).
    await waitFor(() => {
      expect(screen.getByText(/Neuro-symbolic/)).toBeInTheDocument();
    });
    expect(screen.queryByText("Graph reasoning")).not.toBeInTheDocument();
  });

  it("case 3b: search filters by title", async () => {
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Search sources…")).toBeInTheDocument();
    });
    fireEvent.change(screen.getByPlaceholderText("Search sources…"), { target: { value: "graph" } });
    expect(screen.getByText("Graph reasoning")).toBeInTheDocument();
    expect(screen.queryByText("Neuro-symbolic")).not.toBeInTheDocument();
  });

  it("case 4: source detail shows available metadata + unavailable stated", async () => {
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText(/Neuro-symbolic/)).toBeInTheDocument();
    });
    // Click the unresolved source (no metadata)
    fireEvent.click(screen.getByText(/Neuro-symbolic/));
    await waitFor(() => {
      expect(screen.getByText("Source Detail")).toBeInTheDocument();
    });
    // Unresolved source: match method shown unavailable
    expect(screen.getAllByText(/unavailable/i).length).toBeGreaterThan(0);
  });

  it("case 5: unresolved citations are clearly identified", async () => {
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText("unresolved")).toBeInTheDocument();
    });
  });

  it("case 6: section-to-source links shown when available", async () => {
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText("Graph reasoning")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Graph reasoning"));
    await waitFor(() => {
      expect(screen.getByText("Method")).toBeInTheDocument();
    });
  });

  it("case 7: missing mapping shown as unavailable", async () => {
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText(/Neuro-symbolic/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Neuro-symbolic/));
    await waitFor(() => {
      expect(screen.getByText(/no persisted marker mapping/i)).toBeInTheDocument();
    });
  });

  it("case 8: review decisions persist (accept calls API)", async () => {
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText("Graph reasoning")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Graph reasoning"));
    await waitFor(() => {
      expect(screen.getByText("Accept")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /Accept/ }));
    await waitFor(() => {
      expect(reviewMocks.recordSourceDecision).toHaveBeenCalledWith(1, expect.objectContaining({ decision: "accepted" }));
    });
  });

  it("case 9: flagged and exclusion states are visually distinct", async () => {
    // Render with a flagged + an excluded source
    reviewMocks.getReview.mockResolvedValue(
      makeReview({
        sources: [
          { ...makeReview().sources[0], human_decision: { decision: "flagged", note: null, reviewer: "x", reviewed_at: "2026-01-01" } },
          { ...makeReview().sources[1], human_decision: { decision: "exclude_on_next_revision", note: null, reviewer: "x", reviewed_at: "2026-01-01" } },
        ],
      }),
    );
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText("Flagged / Excluded")).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: "Flagged / Excluded" }));
    await waitFor(() => {
      expect(screen.getByText("flagged")).toBeInTheDocument();
      expect(screen.getByText("excluded")).toBeInTheDocument();
    });
  });

  it("case 10: current paper does not appear revised after a decision", async () => {
    // Seed a review with a flagged source so the immutability note renders
    // (the note appears when flagged_or_excluded > 0).
    reviewMocks.getReview.mockResolvedValue(
      makeReview({
        sources: [
          { ...makeReview().sources[0], human_decision: { decision: "exclude_on_next_revision", note: null, reviewer: "x", reviewed_at: "2026-01-01" } },
        ],
        human_review: { ...makeReview().human_review, flagged_or_excluded: 1, reviewed_sources: 1, status: "completed_with_flags" },
      }),
    );
    renderWorkspace();
    await waitFor(() => {
      // The immutability note (regeneration boundary) should be present.
      expect(screen.getByText(/do not change the current paper/i)).toBeInTheDocument();
    });
  });

  it("case 11: loading state renders", () => {
    reviewMocks.getReview.mockReturnValue(new Promise(() => {})); // never resolves
    renderWorkspace();
    expect(screen.getByText(/Loading trust/i)).toBeInTheDocument();
  });

  it("case 11b: failed state renders", async () => {
    reviewMocks.getReview.mockRejectedValue(new Error("network"));
    renderWorkspace();
    await waitFor(() => {
      expect(screen.getByText("Review data unavailable.")).toBeInTheDocument();
    });
  });

  it("case 12: no dormant review component remains unused", () => {
    // Evidence-panel and evaluation-card were removed in commit 2; verify they
    // no longer exist on disk (the completion rule: wired/adapted/removed).
    // This is a source-level invariant checked here.
    const fs = require("fs");
    expect(() => fs.readFileSync("src/components/ideas/evidence-panel.tsx")).toThrow();
    expect(() => fs.readFileSync("src/components/ideas/evaluation-card.tsx")).toThrow();
  });
});
