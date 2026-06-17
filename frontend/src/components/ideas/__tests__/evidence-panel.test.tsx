/**
 * Tests for EvidencePanel component.
 * Phase B: Source Traceability & Evidence UX.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { EvidencePanel } from "@/components/ideas/evidence-panel";
import type { SourceGap, UnresolvedSourceGap, ProposalReference } from "@/api/types";

function renderPanel(props: {
  sourceGaps?: (SourceGap | UnresolvedSourceGap)[] | null;
  proposalReferences?: ProposalReference[] | string | null;
  mechanicalMetrics?: Record<string, number> | null;
}) {
  return render(
    <MemoryRouter>
      <EvidencePanel
        sourceGaps={props.sourceGaps ?? null}
        proposalReferences={props.proposalReferences ?? null}
        mechanicalMetrics={props.mechanicalMetrics ?? null}
      />
    </MemoryRouter>,
  );
}

const resolvedGaps: SourceGap[] = [
  { id: 1, title: "Limited cross-domain eval", gap_type: "empirical", confidence: 0.85, resolved: true },
  { id: 2, title: "No real-time optimization", gap_type: "methodological", confidence: 0.70, resolved: true },
];

const unresolvedGaps: UnresolvedSourceGap[] = [
  { raw: "some-unresolved-hash-ref", resolved: false },
];

const mixedGaps: (SourceGap | UnresolvedSourceGap)[] = [
  ...resolvedGaps,
  ...unresolvedGaps,
];

const sampleRefs: ProposalReference[] = [
  { raw: "Smith et al. (2024). Attention Transfer. NeurIPS." },
  { raw: "Jones et al. (2023). Cross-Domain Eval. ICML." },
];

const sampleMetrics: Record<string, number> = {
  citation_density: 0.456,
  prior_art_distance: 0.789,
  coverage_score: 0.123,
};

describe("EvidencePanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Source Gaps ──────────────────────────────────────────────

  it("renders nothing when all data is null", () => {
    const { container } = renderPanel({});
    expect(container.firstChild).toBeNull();
  });

  it("renders resolved source gaps with titles and links", () => {
    renderPanel({ sourceGaps: resolvedGaps });
    expect(screen.getByTestId("evidence-panel")).toBeInTheDocument();
    expect(screen.getByText("Evidence & Provenance")).toBeInTheDocument();
    expect(screen.getByText("Limited cross-domain eval")).toBeInTheDocument();
    expect(screen.getByText("No real-time optimization")).toBeInTheDocument();
  });

  it("source gap links navigate to /gaps/:id via onClick", () => {
    renderPanel({ sourceGaps: resolvedGaps });
    const link = screen.getByTestId("source-gap-link-0");
    expect(link).toBeInTheDocument();
    expect(link.tagName).toBe("BUTTON");
  });

  it("renders gap type and confidence for resolved gaps", () => {
    renderPanel({ sourceGaps: resolvedGaps });
    expect(screen.getByText("empirical")).toBeInTheDocument();
    expect(screen.getByText("methodological")).toBeInTheDocument();
    expect(screen.getByText("85% conf.")).toBeInTheDocument();
  });

  it("renders unresolved gaps with raw text and unresolved badge", () => {
    renderPanel({ sourceGaps: unresolvedGaps });
    expect(screen.getByText("some-unresolved-hash-ref")).toBeInTheDocument();
    expect(screen.getByText("unresolved")).toBeInTheDocument();
  });

  it("renders mixed resolved and unresolved gaps together", () => {
    renderPanel({ sourceGaps: mixedGaps });
    // Resolved
    expect(screen.getByText("Limited cross-domain eval")).toBeInTheDocument();
    // Unresolved
    expect(screen.getByText("some-unresolved-hash-ref")).toBeInTheDocument();
    expect(screen.getByText("unresolved")).toBeInTheDocument();
  });

  // ── Proposal References ──────────────────────────────────────

  it("renders proposal references as list of {raw} items", () => {
    renderPanel({ proposalReferences: sampleRefs });
    expect(screen.getByText("Smith et al. (2024). Attention Transfer. NeurIPS.")).toBeInTheDocument();
    expect(screen.getByText("Jones et al. (2023). Cross-Domain Eval. ICML.")).toBeInTheDocument();
  });

  it("renders string references as preformatted text", () => {
    renderPanel({ proposalReferences: "Raw reference text block" });
    expect(screen.getByText("Raw reference text block")).toBeInTheDocument();
  });

  // ── Mechanical Metrics Provenance ────────────────────────────

  it("renders mechanical metrics with formatted keys", () => {
    renderPanel({ mechanicalMetrics: sampleMetrics });
    expect(screen.getByText(/Citation Density/i)).toBeInTheDocument();
    expect(screen.getByText("0.456")).toBeInTheDocument();
    expect(screen.getByText("0.789")).toBeInTheDocument();
  });

  // ── All sections together ────────────────────────────────────

  it("renders all three sections when all data present", () => {
    renderPanel({
      sourceGaps: resolvedGaps,
      proposalReferences: sampleRefs,
      mechanicalMetrics: sampleMetrics,
    });
    expect(screen.getByTestId("evidence-source-gaps")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-references")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-metrics-provenance")).toBeInTheDocument();
  });

  it("renders only source gaps when references and metrics are null", () => {
    renderPanel({ sourceGaps: resolvedGaps });
    expect(screen.getByTestId("evidence-source-gaps")).toBeInTheDocument();
    expect(screen.queryByTestId("evidence-references")).not.toBeInTheDocument();
    expect(screen.queryByTestId("evidence-metrics-provenance")).not.toBeInTheDocument();
  });
});
