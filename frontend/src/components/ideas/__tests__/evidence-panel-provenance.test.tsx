import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { EvidencePanel } from "@/components/ideas/evidence-panel";
import type {
  SupportingPaper,
  ResolvedReference,
} from "@/api/types";

function renderPanel(props: Parameters<typeof EvidencePanel>[0]) {
  return render(
    <MemoryRouter>
      <EvidencePanel {...props} />
    </MemoryRouter>,
  );
}

const samplePaper: SupportingPaper = {
  id: 1,
  title: "Attention Is All You Need",
  year: 2017,
  venue: "NeurIPS",
  citation_count: 50000,
  doi: "10.1234/attention",
  arxiv_id: "1706.03762",
  url: "https://example.com",
  role: "supporting",
};

const resolvedRef: ResolvedReference = {
  raw: "[1] Vaswani et al. (2017). Attention Is All You Need.",
  number: 1,
  authors: "Vaswani et al.",
  year: "2017",
  title: "Attention Is All You Need",
  venue: "NeurIPS",
  resolved: true,
  paper: { id: 1, title: "Attention Is All You Need", year: 2017, venue: "NeurIPS", doi: null, arxiv_id: null, url: null },
  match_method: "title_exact",
  match_confidence: 0.95,
};

const unresolvedRef: ResolvedReference = {
  raw: "[2] Unknown (2024). Some Random Paper.",
  number: 2,
  authors: "Unknown",
  year: "2024",
  title: "Some Random Paper",
  venue: null,
  resolved: false,
  paper: null,
  match_method: null,
  match_confidence: 0,
};

describe("EvidencePanel — Supporting Papers", () => {
  it("renders supporting papers when provided", () => {
    renderPanel({
      sourceGaps: null,
      supportingPapers: [samplePaper],
      proposalReferences: null,
      mechanicalMetrics: null,
    });

    expect(screen.getByTestId("evidence-supporting-papers")).toBeInTheDocument();
    expect(screen.getByText("Attention Is All You Need")).toBeInTheDocument();
    expect(screen.getByText("supporting")).toBeInTheDocument();
  });

  it("shows paper metadata (year, venue, citations)", () => {
    renderPanel({
      sourceGaps: null,
      supportingPapers: [samplePaper],
      proposalReferences: null,
      mechanicalMetrics: null,
    });

    expect(screen.getByText("2017")).toBeInTheDocument();
    expect(screen.getByText("NeurIPS")).toBeInTheDocument();
    expect(screen.getByText(/50,000 citations/)).toBeInTheDocument();
  });

  it("shows DOI and arXiv links when available", () => {
    renderPanel({
      sourceGaps: null,
      supportingPapers: [samplePaper],
      proposalReferences: null,
      mechanicalMetrics: null,
    });

    const doiLink = screen.getByText("DOI");
    expect(doiLink.closest("a")).toHaveAttribute(
      "href",
      "https://doi.org/10.1234/attention",
    );

    const arxivLink = screen.getByText("arXiv");
    expect(arxivLink.closest("a")).toHaveAttribute(
      "href",
      "https://arxiv.org/abs/1706.03762",
    );
  });

  it("shows paper count in header", () => {
    renderPanel({
      sourceGaps: null,
      supportingPapers: [samplePaper, { ...samplePaper, id: 2, title: "Second Paper" }],
      proposalReferences: null,
      mechanicalMetrics: null,
    });

    expect(screen.getByText(/Supporting Papers \(2\)/)).toBeInTheDocument();
  });

  it("does not render supporting papers section when null", () => {
    const { container } = renderPanel({
      sourceGaps: null,
      supportingPapers: null,
      proposalReferences: null,
      mechanicalMetrics: null,
    });

    expect(container).toBeEmptyDOMElement();
  });
});

describe("EvidencePanel — Structured References", () => {
  it("renders resolved references with match info", () => {
    renderPanel({
      sourceGaps: null,
      supportingPapers: null,
      proposalReferences: [resolvedRef],
      mechanicalMetrics: null,
    });

    expect(screen.getByTestId("evidence-references")).toBeInTheDocument();
    expect(screen.getByText(/Resolved Proposal References/)).toBeInTheDocument();
    expect(screen.getByText("title_exact")).toBeInTheDocument();
    expect(screen.getByText("95% confidence")).toBeInTheDocument();
  });

  it("shows unresolved badge for unmatched references", () => {
    renderPanel({
      sourceGaps: null,
      supportingPapers: null,
      proposalReferences: [unresolvedRef],
      mechanicalMetrics: null,
    });

    expect(screen.getByText(/Unresolved References/)).toBeInTheDocument();
    expect(screen.getAllByText("unresolved").length).toBeGreaterThan(0);
  });

  it("shows correct resolved/unresolved counts in header", () => {
    renderPanel({
      sourceGaps: null,
      supportingPapers: null,
      proposalReferences: [resolvedRef, unresolvedRef],
      mechanicalMetrics: null,
    });

    expect(screen.getByText(/1\/2/)).toBeInTheDocument();
  });

  it("renders reference match method badge", () => {
    renderPanel({
      sourceGaps: null,
      supportingPapers: null,
      proposalReferences: [resolvedRef],
      mechanicalMetrics: null,
    });

    expect(screen.getByText("title_exact")).toBeInTheDocument();
  });

  it("shows matched paper title for resolved references", () => {
    renderPanel({
      sourceGaps: null,
      supportingPapers: null,
      proposalReferences: [resolvedRef],
      mechanicalMetrics: null,
    });

    expect(screen.getByText(/matched to/)).toBeInTheDocument();
  });
});

describe("EvidencePanel — Empty states", () => {
  it("renders nothing when all props are null", () => {
    const { container } = renderPanel({
      sourceGaps: null,
      supportingPapers: null,
      proposalReferences: null,
      mechanicalMetrics: null,
    });

    expect(container).toBeEmptyDOMElement();
  });
});
