/**
 * BATCH-13 / TASK-01 — Pipeline Form Completion Tests
 * TEST-13-01-01 through TEST-13-01-06
 */
import { describe, it, expect, vi } from "vitest";
import { renderWithProviders } from "@/test/test-utils";
import { RunConfigForm, VALIDATION } from "@/components/pipeline/run-config-form";
import type { PipelineRunRequest } from "@/api/types";

// ── TEST-13-01-01: generation_rounds input renders with range 1-10 ─────
it("TEST-13-01-01: generation_rounds input renders with range 1-10", () => {
  const { getByTestId } = renderWithProviders(
    <RunConfigForm onSubmit={vi.fn()} />,
  );
  const input = getByTestId("generation-rounds-input") as HTMLInputElement;
  expect(input).toBeInTheDocument();
  expect(input.type).toBe("number");
  expect(Number(input.min)).toBe(VALIDATION.generation_rounds.min);
  expect(Number(input.max)).toBe(VALIDATION.generation_rounds.max);
  expect(Number(input.value)).toBe(VALIDATION.generation_rounds.default);
});

// ── TEST-13-01-02: export_format dropdown renders with 2 options ──────
it("TEST-13-01-02: export_format dropdown renders with 2 options", () => {
  const { getByTestId } = renderWithProviders(
    <RunConfigForm onSubmit={vi.fn()} />,
  );
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

// ── TEST-13-01-04: Toggles for novelty/feasibility/synthesis render ───
it("TEST-13-01-04: toggles for novelty/feasibility/synthesis render in advanced section", async () => {
  const { user, getByTestId } = renderWithProviders(
    <RunConfigForm onSubmit={vi.fn()} />,
  );
  // Open advanced section first
  await user.click(getByTestId("advanced-toggle"));

  const noveltyToggle = getByTestId("run-novelty-toggle") as HTMLInputElement;
  const feasibilityToggle = getByTestId("run-feasibility-toggle") as HTMLInputElement;
  const synthesisToggle = getByTestId("run-synthesis-toggle") as HTMLInputElement;

  expect(noveltyToggle).toBeInTheDocument();
  expect(feasibilityToggle).toBeInTheDocument();
  expect(synthesisToggle).toBeInTheDocument();

  // Default should be checked (true)
  expect(noveltyToggle.checked).toBe(true);
  expect(feasibilityToggle.checked).toBe(true);
  expect(synthesisToggle.checked).toBe(true);
});

// ── TEST-13-01-05: max_gaps range is 1-20 (not 1-50) ──────────────────
it("TEST-13-01-05: max_gaps range is 1-20 (not 1-50)", () => {
  const { getByTestId } = renderWithProviders(
    <RunConfigForm onSubmit={vi.fn()} />,
  );
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

  // Open advanced section and toggle off novelty
  await user.click(getByTestId("advanced-toggle"));
  await user.click(getByTestId("run-novelty-toggle"));

  // Change export format to latex
  const select = getByTestId("export-format-select") as HTMLSelectElement;
  await user.selectOptions(select, "latex");

  // Change generation rounds
  const genRoundsInput = getByTestId("generation-rounds-input");
  await user.clear(genRoundsInput);
  await user.type(genRoundsInput, "5");

  // Submit
  await user.click(getByText("Start Pipeline"));

  expect(onSubmit).toHaveBeenCalledOnce();
  const config = onSubmit.mock.calls[0][0] as PipelineRunRequest;

  // Verify all new fields are present
  expect(config.domain).toBe("quantum computing");
  expect(config.generation_rounds).toBe(5);
  expect(config.export_format).toBe("latex");
  expect(config.run_novelty).toBe(false);
  expect(config.run_feasibility).toBe(true);
  expect(config.run_synthesis).toBe(true);
  expect(config.max_gaps).toBe(VALIDATION.max_gaps.default);
});
