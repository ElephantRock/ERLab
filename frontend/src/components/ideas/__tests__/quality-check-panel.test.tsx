import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { QualityCheckPanel } from "@/components/ideas/quality-check-panel";
import type { QualityCheckResult, RemediationHint } from "@/api/types";

const passingCheck: QualityCheckResult = {
  section: "abstract",
  label: "Abstract",
  present: true,
  word_count: 200,
  min_words: 150,
  meets_word_count: true,
  checks: [],
  passed: true,
  failures: [],
};

const failingCheck: QualityCheckResult = {
  section: "proposed_method",
  label: "Proposed Method",
  present: true,
  word_count: 100,
  min_words: 600,
  meets_word_count: false,
  checks: [
    { name: "formal loss function", passed: true },
    { name: "training objective", passed: false },
  ],
  passed: false,
  failures: ["word count 100 < 600", "missing training objective"],
};

const missingCheck: QualityCheckResult = {
  section: "timeline",
  label: "Timeline",
  present: false,
  word_count: 0,
  min_words: 100,
  meets_word_count: false,
  checks: [],
  passed: false,
  failures: [],
};

describe("QualityCheckPanel", () => {
  it("renders nothing when qualityChecks is null", () => {
    const { container } = render(<QualityCheckPanel qualityChecks={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when qualityChecks is empty array", () => {
    const { container } = render(<QualityCheckPanel qualityChecks={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders summary badge with passed/total count", () => {
    render(
      <QualityCheckPanel
        qualityChecks={[passingCheck, failingCheck, missingCheck]}
      />,
    );

    const summary = screen.getByTestId("quality-check-summary");
    expect(summary).toHaveTextContent("1/3 sections passed");
  });

  it("renders all sections", () => {
    render(
      <QualityCheckPanel
        qualityChecks={[passingCheck, failingCheck, missingCheck]}
      />,
    );

    expect(screen.getByTestId("quality-check-abstract")).toBeInTheDocument();
    expect(
      screen.getByTestId("quality-check-proposed_method"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("quality-check-timeline")).toBeInTheDocument();
  });

  it("shows word count for present sections", () => {
    render(<QualityCheckPanel qualityChecks={[failingCheck]} />);

    expect(screen.getByText("100/600 words")).toBeInTheDocument();
  });

  it("shows pattern check chips for sections with checks", () => {
    render(<QualityCheckPanel qualityChecks={[failingCheck]} />);

    expect(screen.getByText("formal loss function")).toBeInTheDocument();
    expect(screen.getByText("training objective")).toBeInTheDocument();
  });

  it("shows 'Section not present' for missing sections", () => {
    render(<QualityCheckPanel qualityChecks={[missingCheck]} />);

    expect(screen.getByText("Section not present in proposal")).toBeInTheDocument();
  });

  it("shows failure descriptions for failing sections", () => {
    render(<QualityCheckPanel qualityChecks={[failingCheck]} />);

    expect(
      screen.getByText(/word count 100 < 600/),
    ).toBeInTheDocument();
  });

  it("shows success styling when all sections pass", () => {
    const allPassing: QualityCheckResult[] = [
      { ...passingCheck },
      { ...passingCheck, section: "introduction", label: "Introduction" },
    ];
    render(<QualityCheckPanel qualityChecks={allPassing} />);

    const summary = screen.getByTestId("quality-check-summary");
    expect(summary).toHaveTextContent("2/2 sections passed");
  });

  it("handles section with checks but no failures", () => {
    const allPatternsPass: QualityCheckResult = {
      ...passingCheck,
      section: "evaluation_plan",
      label: "Evaluation Plan",
      checks: [
        { name: "named baselines", passed: true },
        { name: "ablation experiments", passed: true },
      ],
    };
    render(<QualityCheckPanel qualityChecks={[allPatternsPass]} />);

    expect(screen.getByText("named baselines")).toBeInTheDocument();
    expect(screen.getByText("ablation experiments")).toBeInTheDocument();
  });

  it("handles all sections missing", () => {
    const allMissing: QualityCheckResult[] = [
      { ...missingCheck },
      { ...missingCheck, section: "abstract", label: "Abstract" },
    ];
    render(<QualityCheckPanel qualityChecks={allMissing} />);

    expect(screen.getByText("No sections found")).toBeInTheDocument();
  });

  // --- Remediation hint tests ---

  const wordCountHint: RemediationHint = {
    section: "proposed_method",
    label: "Proposed Method",
    issue_type: "word_count",
    severity: "warning",
    message: "word count 100 < 600",
    suggestion: "Expand this section to at least 600 words.",
    refinement_available: true,
  };

  const patternHint: RemediationHint = {
    section: "proposed_method",
    label: "Proposed Method",
    issue_type: "missing_pattern",
    severity: "warning",
    message: "missing training objective",
    suggestion: "Explicitly state the loss function or optimization objective.",
    refinement_available: true,
  };

  it("renders remediation hints inline for failing sections", () => {
    render(
      <QualityCheckPanel
        qualityChecks={[failingCheck]}
        remediationHints={[wordCountHint, patternHint]}
      />,
    );

    const hintBlock = screen.getByTestId(
      "remediation-inline-proposed_method",
    );
    expect(hintBlock).toBeInTheDocument();
    expect(
      screen.getByText("Expand this section to at least 600 words."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Explicitly state the loss function or optimization objective.",
      ),
    ).toBeInTheDocument();
  });

  it("does not render hints for passing sections", () => {
    render(
      <QualityCheckPanel
        qualityChecks={[passingCheck, failingCheck]}
        remediationHints={[wordCountHint]}
      />,
    );

    // Hint shows for proposed_method (failing) but not abstract (passing)
    expect(
      screen.queryByTestId("remediation-inline-abstract"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("remediation-inline-proposed_method"),
    ).toBeInTheDocument();
  });

  it("does not render hints block when no hints provided", () => {
    render(<QualityCheckPanel qualityChecks={[failingCheck]} />);

    expect(
      screen.queryByTestId("remediation-inline-proposed_method"),
    ).not.toBeInTheDocument();
  });

  it("does not render hints block when hints is null", () => {
    render(
      <QualityCheckPanel qualityChecks={[failingCheck]} remediationHints={null} />,
    );

    expect(
      screen.queryByTestId("remediation-inline-proposed_method"),
    ).not.toBeInTheDocument();
  });
});
