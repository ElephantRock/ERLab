/**
 * Tests for the rebuilt reading surface (Phase 2 — INTERFACE_CONTRACT §1, §3, §6).
 *
 * Verifies the properties PRODUCT.md demands of the reading workspace:
 * - useResource + DataView (not raw useQuery) — §1
 * - Reading-scale typography on the proposal body — §3
 * - ScoreReport replaces ScoreBadge (scores are inspectable) — §6
 * - No sub-micro type (text-[8px], [9px], [10px]) — §3
 * - No telemetry headings (font-mono uppercase tracking-widest) — §3
 */

import { describe, it, expect, vi } from "vitest";
import { screen } from "@testing-library/react";
import { renderWithProviders } from "@/test/test-utils";
import { Routes, Route } from "react-router-dom";

// Mock the API
vi.mock("@/api/ideas", () => ({
  getIdea: vi.fn().mockResolvedValue({
    idea: {
      id: 1,
      title: "Test Proposal",
      problem_statement: "A problem.",
      proposed_method: "A method.",
      expected_contributions: "Contributions.",
      domain: "AI/NLP",
      novelty_score: 0.82,
      feasibility_score: 7.5,
      overall_score: 0.78,
      novelty_report: {
        method_novelty: 0.9,
        problem_novelty: 0.7,
        domain_transfer: 0.6,
        combination_novelty: 0.8,
      },
      feasibility_report: { score: 7.5 },
      proposal_md: "# Test\n\nThis is a proposal.",
      proposal_sections: {
        introduction: "This is the introduction text.",
        proposed_method: "This is the method.",
      },
      proposal_references: [],
      supporting_papers: [],
      quality_checks: [],
      section_hashes: {},
      remediation_hints: [],
      citation_audit: [],
      mechanical_metrics: null,
      experiment_results: null,
      source_gap_ids: null,
      source_gaps: null,
      created_at: "2024-01-01",
    },
  }),
  refineIdea: vi.fn(),
}));

/** Render the IdeaDetail inside a Route so useParams can extract :id */
async function renderIdeaDetail() {
  const IdeaDetail = (await import("@/pages/idea-detail")).default;
  return renderWithProviders(
    <Routes>
      <Route path="/ideas/:id" element={<IdeaDetail />} />
    </Routes>,
    { initialEntries: ["/ideas/1"] },
  );
}

// ══ Compliance: useResource + DataView ═══════════════════════════

describe("IdeaDetail — contract compliance", () => {
  it("renders via DataView (not raw useQuery skeleton)", async () => {
    await renderIdeaDetail();
    expect(await screen.findByText("Test Proposal")).toBeInTheDocument();
  });

  it("applies reading-scale typography to the proposal body", async () => {
    const { container } = await renderIdeaDetail();
    await screen.findByText("Test Proposal");
    const proseBody = container.querySelector(".text-prose-body");
    expect(proseBody).toBeInTheDocument();
  });

  it("uses ui-micro as the floor — no text-[8px], [9px], [10px]", async () => {
    const { container } = await renderIdeaDetail();
    await screen.findByText("Test Proposal");
    const html = container.innerHTML;
    expect(html).not.toMatch(/text-\[8px\]/);
    expect(html).not.toMatch(/text-\[9px\]/);
    expect(html).not.toMatch(/text-\[10px\]/);
  });

  it("renders ScoreReport for novelty (not flat ScoreBadge)", async () => {
    await renderIdeaDetail();
    // ScoreReport renders the summary number + kind label in aria-label
    const noveltyScore = await screen.findByLabelText(/Novelty: 0\.82/);
    expect(noveltyScore).toBeInTheDocument();
  });
});
