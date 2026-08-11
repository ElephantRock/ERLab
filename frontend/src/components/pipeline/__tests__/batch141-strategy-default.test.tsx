import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RunConfigForm } from "@/components/pipeline/run-config-form";
import type { PipelineRunRequest } from "@/api/types";

// ── Helpers ──────────────────────────────────────────────────────

function renderForm(overrides?: { onSubmit?: (config: PipelineRunRequest) => void }) {
  const onSubmit = overrides?.onSubmit ?? vi.fn();
  const result = render(
    <RunConfigForm onSubmit={onSubmit} />,
  );
  return { ...result, onSubmit };
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});

describe("BATCH-141 / TASK-01: Strategy Default Change", () => {
  // ── TEST-141-01-01: Default strategy state is "fast_scan" on mount ──
  // Falsified by: changing useState back to "deep_research" in run-config-form.tsx

  it("TEST-141-01-01: defaults to fast_scan on mount", () => {
    renderForm();

    const select = screen.getByTestId("strategy-select") as HTMLSelectElement;
    expect(select.value).toBe("fast_scan");
  });

  // ── TEST-141-01-02: Strategy select has 4 options with correct values ──
  // Falsified by: removing one <option> from the <select> in run-config-form.tsx

  it("TEST-141-01-02: strategy select has all 4 strategy options", () => {
    renderForm();

    const select = screen.getByTestId("strategy-select") as HTMLSelectElement;
    const options = Array.from(select.options);

    const values = options.map((o) => o.value);
    expect(values).toContain("fast_scan");
    expect(values).toContain("deep_research");
    expect(values).toContain("academic_proposal");
    expect(values).toContain("literature_review");
    expect(options.length).toBe(4);
  });

  // ── TEST-141-01-03: fast_scan truthfully describes its output ──
  // Falsified by: restoring the old "skips tree search and metrics" copy
  // without saying that lightweight ideas and proposals are still produced.

  it("TEST-141-01-03: fast_scan describes lightweight ideas and concise proposals", () => {
    renderForm();

    const card = screen.getByTestId("strategy-card-fast_scan");
    expect(card).toHaveTextContent(/lightweight ideas/i);
    expect(card).toHaveTextContent(/concise proposals/i);
  });

  // ── TEST-141-01-04: deep_research truthfully describes full workflow ──
  // Falsified by: reverting to a proposal-only description.

  it("TEST-141-01-04: deep_research describes the proposal-to-paper workflow", () => {
    renderForm();

    const card = screen.getByTestId("strategy-card-deep_research");
    expect(card).toHaveTextContent(/proposal-to-paper workflow/i);
  });

  // ── TEST-141-01-05: Submitted config includes strategy="fast_scan" by default ──
  // Falsified by: changing default back to "deep_research" in useState

  it("TEST-141-01-05: form submission includes strategy=fast_scan by default", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    renderForm({ onSubmit });

    // Phase 1 1B: supply a research question so the submission is valid under
    // the new contract (question or domain required). The test's invariant is
    // the strategy default, not the empty-submission behavior.
    const rq = screen.getByTestId("research-question-input");
    await user.type(rq, "Test research question");

    const submitBtn = screen.getByRole("button", { name: /start pipeline/i });
    await user.click(submitBtn);

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const submittedConfig = onSubmit.mock.calls[0][0] as PipelineRunRequest;
    expect(submittedConfig.strategy).toBe("fast_scan");
  });

  // ── TEST-141-01-06: Changing strategy updates the description text ──
  // Falsified by: removing the onChange handler from the strategy select

  it("TEST-141-01-06: changing strategy updates description text", async () => {
    const user = userEvent.setup();
    renderForm();

    // Default card shows fast_scan description
    expect(screen.getByText(/Rapid gaps → lightweight ideas → concise proposals/)).toBeInTheDocument();

    // Click deep_research card
    await user.click(screen.getByTestId("strategy-card-deep_research"));

    // Description should now show deep_research text
    expect(screen.getByText(/Full proposal-to-paper workflow/)).toBeInTheDocument();
  });
});
