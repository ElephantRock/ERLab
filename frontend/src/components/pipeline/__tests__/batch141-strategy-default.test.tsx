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

  // ── TEST-141-01-03: fast_scan option shows correct time estimate ──
  // Falsified by: changing the fast_scan option text to empty string

  it("TEST-141-01-03: fast_scan option shows time estimate", () => {
    renderForm();

    const select = screen.getByTestId("strategy-select") as HTMLSelectElement;
    const fastScanOption = Array.from(select.options).find((o) => o.value === "fast_scan");
    expect(fastScanOption?.textContent).toMatch(/2-5 min/);
  });

  // ── TEST-141-01-04: deep_research option shows "~25 min" time estimate ──
  // Falsified by: changing the deep_research option text to empty string

  it("TEST-141-01-04: deep_research option shows 25 min time estimate", () => {
    renderForm();

    const select = screen.getByTestId("strategy-select") as HTMLSelectElement;
    const deepOption = Array.from(select.options).find((o) => o.value === "deep_research");
    expect(deepOption?.textContent).toMatch(/25 min/);
  });

  // ── TEST-141-01-05: Submitted config includes strategy="fast_scan" by default ──
  // Falsified by: changing default back to "deep_research" in useState

  it("TEST-141-01-05: form submission includes strategy=fast_scan by default", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    renderForm({ onSubmit });

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

    // Default should show fast_scan description
    expect(screen.getByText(/Fast scan skips tree search/)).toBeInTheDocument();

    // Change to deep_research
    const select = screen.getByTestId("strategy-select");
    await user.selectOptions(select, "deep_research");

    // Description should now show deep_research text
    expect(screen.getByText(/Full pipeline with tree search/)).toBeInTheDocument();
    expect(screen.queryByText(/Fast scan skips tree search/)).not.toBeInTheDocument();
  });
});
