import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RemediationBanner } from "@/components/ideas/remediation-banner";
import type { RemediationHint, CitationAuditEntry } from "@/api/types";

const wordCountHint: RemediationHint = {
  section: "introduction",
  label: "Introduction",
  issue_type: "word_count",
  severity: "warning",
  message: "word count 50 < 400",
  suggestion: "Expand this section to at least 400 words.",
  refinement_available: true,
};

const patternHint: RemediationHint = {
  section: "related_work",
  label: "Related Work",
  issue_type: "missing_pattern",
  severity: "warning",
  message: "missing citation markers",
  suggestion: "Add inline references like [1] or (Author, Year).",
  refinement_available: true,
};

const missingSectionHint: RemediationHint = {
  section: "timeline",
  label: "Timeline",
  issue_type: "missing_section",
  severity: "error",
  message: "Section not present in proposal",
  suggestion: "The Timeline section is missing entirely.",
  refinement_available: true,
};

const citationAudit: CitationAuditEntry[] = [
  {
    section: "related_work",
    label: "Related Work",
    citation_needed_count: 2,
    valid_citation_count: 3,
    has_citation_issues: true,
    resolved_reference_count: 3,
    unresolved_reference_count: 1,
  },
  {
    section: "_summary",
    label: "All Sections",
    citation_needed_count: 2,
    valid_citation_count: 3,
    has_citation_issues: true,
  },
];

describe("RemediationBanner", () => {
  it("renders nothing when remediationHints is null", () => {
    const { container } = render(
      <RemediationBanner remediationHints={null} citationAudit={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when remediationHints is empty", () => {
    const { container } = render(
      <RemediationBanner remediationHints={[]} citationAudit={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders summary with issue counts when hints exist", () => {
    render(
      <RemediationBanner
        remediationHints={[wordCountHint, patternHint, missingSectionHint]}
        citationAudit={null}
      />,
    );

    expect(screen.getByText("Quality issues detected")).toBeInTheDocument();
    expect(screen.getByText("1 missing section")).toBeInTheDocument();
    expect(screen.getByText("1 word count")).toBeInTheDocument();
    expect(screen.getByText("1 missing pattern")).toBeInTheDocument();
  });

  it("shows citation needed badge when audit has issues", () => {
    render(
      <RemediationBanner
        remediationHints={[patternHint]}
        citationAudit={citationAudit}
      />,
    );

    expect(screen.getByText("2 citation needed")).toBeInTheDocument();
  });

  it("expands to show hints when clicked", () => {
    render(
      <RemediationBanner
        remediationHints={[wordCountHint, patternHint]}
        citationAudit={citationAudit}
      />,
    );

    // Initially collapsed — hints not visible
    expect(screen.queryByTestId("remediation-hints-list")).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(screen.getByTestId("remediation-toggle"));

    // Now hints are visible
    expect(screen.getByTestId("remediation-hints-list")).toBeInTheDocument();
    expect(
      screen.getByText("Expand this section to at least 400 words."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Add inline references like [1] or (Author, Year)."),
    ).toBeInTheDocument();
  });

  it("shows citation issues section when expanded", () => {
    render(
      <RemediationBanner
        remediationHints={[patternHint]}
        citationAudit={citationAudit}
      />,
    );

    fireEvent.click(screen.getByTestId("remediation-toggle"));

    expect(screen.getByTestId("remediation-citation-issues")).toBeInTheDocument();
    expect(screen.getByText("2 [Citation needed]")).toBeInTheDocument();
    expect(screen.getByText("3/4 refs resolved")).toBeInTheDocument();
  });

  it("collapses when clicked again", () => {
    render(
      <RemediationBanner
        remediationHints={[wordCountHint]}
        citationAudit={null}
      />,
    );

    // Expand
    fireEvent.click(screen.getByTestId("remediation-toggle"));
    expect(screen.getByTestId("remediation-hints-list")).toBeInTheDocument();

    // Collapse
    fireEvent.click(screen.getByTestId("remediation-toggle"));
    expect(screen.queryByTestId("remediation-hints-list")).not.toBeInTheDocument();
  });

  it("does not show citation badge when no citation issues", () => {
    const cleanAudit: CitationAuditEntry[] = [
      {
        section: "_summary",
        label: "All Sections",
        citation_needed_count: 0,
        valid_citation_count: 5,
        has_citation_issues: false,
      },
    ];

    render(
      <RemediationBanner
        remediationHints={[wordCountHint]}
        citationAudit={cleanAudit}
      />,
    );

    expect(screen.queryByText(/citation needed/)).not.toBeInTheDocument();
  });

  it("shows error icon for missing_section severity", () => {
    render(
      <RemediationBanner
        remediationHints={[missingSectionHint]}
        citationAudit={null}
      />,
    );

    fireEvent.click(screen.getByTestId("remediation-toggle"));

    const hint = screen.getByTestId("remediation-hint-timeline");
    expect(hint).toBeInTheDocument();
  });

  it("shows multiple word count issues with correct badge count", () => {
    const hints: RemediationHint[] = [
      { ...wordCountHint, section: "introduction", label: "Introduction" },
      { ...wordCountHint, section: "abstract", label: "Abstract" },
      { ...wordCountHint, section: "timeline", label: "Timeline" },
    ];

    render(
      <RemediationBanner remediationHints={hints} citationAudit={null} />,
    );

    expect(screen.getByText("3 word count")).toBeInTheDocument();
  });
});
