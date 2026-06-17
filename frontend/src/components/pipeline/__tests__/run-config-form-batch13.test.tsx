/**
 * BATCH-13 / TASK-01 — Pipeline Form Completion Tests
 * TEST-13-01-01 through TEST-13-01-06
 */
import { describe, it, expect, vi } from "vitest";
import { renderWithProviders } from "@/test/test-utils";
import { RunConfigForm, VALIDATION } from "@/components/pipeline/run-config-form";
import type { PipelineRunRequest } from "@/api/types";

// Mock the estimate endpoint used by EstimateCard inside RunConfigForm
vi.mock("@/api/pipeline", () => ({
  getEstimate: vi.fn().mockResolvedValue({
    strategy: "fast_scan",
    stages: 3,
    estimated_cost_usd: 0,
    estimated_time_seconds: 120,
    estimated_time_display: "~2 min",
    cost_display: "$0.00",
    local_cost_usd: 0,
    cloud_cost_usd: 0,
    breakdown: [],
  }),
}));

// ── TEST-13-01-01: generation_rounds input renders with range 1-10 ─────
it("TEST-13-01-01: generation_rounds input renders with range 1-10", async () => {
  const { user, getByTestId } = renderWithProviders(
    <RunConfigForm onSubmit={vi.fn()} />,
  );
  // Open advanced section first
  await user.click(getByTestId("advanced-toggle"));
  const input = getByTestId("generation-rounds-input") as HTMLInputElement;
  expect(input).toBeInTheDocument();
  expect(input.type).toBe("number");
  expect(Number(input.min)).toBe(VALIDATION.generation_rounds.min);
  expect(Number(input.max)).toBe(VALIDATION.generation_rounds.max);
  expect(Number(input.value)).toBe(VALIDATION.generation_rounds.default);
});

// ── TEST-13-01-02: export_format dropdown renders with 2 options ──────
it("TEST-13-01-02: export_format dropdown renders with 2 options", async () => {
  const { user, getByTestId } = renderWithProviders(
    <RunConfigForm onSubmit={vi.fn()} />,
  );
  // Open advanced section first
  await user.click(getByTestId("advanced-toggle"));
  const select = getByTestId("export-format-select") as HTMLSelectElement;
  expect(select).toBeInTheDocument();
  const options = Array.from(select.options);
  expect(options).toHaveLength(2);
  const optionValues = options.map((o) => o.value);
  expect(optionValues).toContain("markdown");
  expect(optionValues).toContain("latex");
});

// ── TEST-13-01-03: Advanced section is collapsed by default ────────────
it("TEST-13-01-03: Advanced section is collapsed by default", () => {
  const { queryByTestId, getByTestId } = renderWithProviders(
    <RunConfigForm onSubmit={vi.fn()} />,
  );
  // Advanced content should NOT be visible
  expect(queryByTestId("advanced-content")).not.toBeInTheDocument();
  // Toggle button should be present
  const toggle = getByTestId("advanced-toggle");
  expect(toggle).toBeInTheDocument();
  expect(toggle.getAttribute("aria-expanded")).toBe("false");
});

// ── TEST-13-01-04: Quality control selectors render in advanced section ───
it("TEST-13-01-04: quality control selectors render in advanced section", async () => {
  const { user, getByTestId } = renderWithProviders(
    <RunConfigForm onSubmit={vi.fn()} />,
  );
  // Open advanced section first
  await user.click(getByTestId("advanced-toggle"));

  // Proposal depth buttons
  expect(getByTestId("proposal-depth-concise")).toBeInTheDocument();
  expect(getByTestId("proposal-depth-standard")).toBeInTheDocument();
  expect(getByTestId("proposal-depth-detailed")).toBeInTheDocument();

  // Novelty depth buttons
  expect(getByTestId("novelty-depth-light")).toBeInTheDocument();
  expect(getByTestId("novelty-depth-standard")).toBeInTheDocument();
  expect(getByTestId("novelty-depth-thorough")).toBeInTheDocument();

  // Idea diversity buttons
  expect(getByTestId("idea-diversity-focused")).toBeInTheDocument();
  expect(getByTestId("idea-diversity-balanced")).toBeInTheDocument();
  expect(getByTestId("idea-diversity-exploratory")).toBeInTheDocument();
});

// ── TEST-13-01-05: max_gaps range is 1-20 (not 1-50) ──────────────────
it("TEST-13-01-05: max_gaps range is 1-20 (not 1-50)", async () => {
  const { user, getByTestId } = renderWithProviders(
    <RunConfigForm onSubmit={vi.fn()} />,
  );
  // Open advanced section first
  await user.click(getByTestId("advanced-toggle"));
  const input = getByTestId("max-gaps-input") as HTMLInputElement;
  expect(input).toBeInTheDocument();
  expect(Number(input.min)).toBe(VALIDATION.max_gaps.min);
  expect(Number(input.max)).toBe(VALIDATION.max_gaps.max);
  // Ensure max is NOT 50
  expect(Number(input.max)).toBe(20);
  // Default should be 5 (matching API schema)
  expect(Number(input.value)).toBe(VALIDATION.max_gaps.default);
});

// ── TEST-13-01-06: Form submission includes all new fields ─────────────
it("TEST-13-01-06: form submission includes all new fields", async () => {
  const onSubmit = vi.fn();
  const { user, getByTestId, getByPlaceholderText, getByText } = renderWithProviders(
    <RunConfigForm onSubmit={onSubmit} />,
  );

  // Set domain
  await user.type(getByPlaceholderText(/machine learning/), "quantum computing");

  // Open advanced section
  await user.click(getByTestId("advanced-toggle"));

  // Change export format to latex
  const select = getByTestId("export-format-select") as HTMLSelectElement;
  await user.selectOptions(select, "latex");

  // Change generation rounds
  const genRoundsInput = getByTestId("generation-rounds-input");
  await user.clear(genRoundsInput);
  await user.type(genRoundsInput, "5");

  // Set quality controls
  await user.click(getByTestId("proposal-depth-detailed"));
  await user.click(getByTestId("novelty-depth-thorough"));
  await user.click(getByTestId("idea-diversity-exploratory"));

  // Submit
  await user.click(getByText("Start Pipeline"));

  expect(onSubmit).toHaveBeenCalledOnce();
  const config = onSubmit.mock.calls[0][0] as PipelineRunRequest;

  // Verify all fields are present
  expect(config.domain).toBe("quantum computing");
  expect(config.generation_rounds).toBe(5);
  expect(config.export_format).toBe("latex");
  expect(config.proposal_depth).toBe("detailed");
  expect(config.novelty_depth).toBe("thorough");
  expect(config.idea_diversity).toBe("exploratory");
  expect(config.max_gaps).toBe(VALIDATION.max_gaps.default);
});
