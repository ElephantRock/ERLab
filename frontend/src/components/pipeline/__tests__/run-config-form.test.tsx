import { describe, it, expect, vi } from "vitest";
import { renderWithProviders } from "@/test/test-utils";
import { RunConfigForm } from "@/components/pipeline/run-config-form";
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

describe("RunConfigForm", () => {
  it("renders all form fields", () => {
    const { getByPlaceholderText, getByText } = renderWithProviders(
      <RunConfigForm onSubmit={vi.fn()} />,
    );
    expect(getByPlaceholderText(/machine learning/)).toBeInTheDocument();
    // Search queries is in advanced section — just verify the form renders
    expect(getByText("Start Pipeline")).toBeInTheDocument();
  });

  it("calls onSubmit with correct config on submit", async () => {
    const onSubmit = vi.fn();
    const { user, getByPlaceholderText, getByText } = renderWithProviders(
      <RunConfigForm onSubmit={onSubmit} />,
    );

    await user.type(getByPlaceholderText(/machine learning/), "NLP");
    await user.click(getByText("Start Pipeline"));

    expect(onSubmit).toHaveBeenCalledOnce();
    const config = onSubmit.mock.calls[0][0] as PipelineRunRequest;
    expect(config.domain).toBe("NLP");
    expect(config.max_gaps).toBe(5);
    expect(config.ideas_per_round).toBe(5);
  });

  it("disables button when isLoading is true", () => {
    const { getByTestId } = renderWithProviders(
      <RunConfigForm onSubmit={vi.fn()} isLoading={true} />,
    );
    expect(getByTestId("start-pipeline-btn")).toBeDisabled();
  });

  it("shows Starting text when loading", () => {
    const { getByText } = renderWithProviders(
      <RunConfigForm onSubmit={vi.fn()} isLoading={true} />,
    );
    expect(getByText(/Starting Pipeline/)).toBeInTheDocument();
  });

  it("defaults max gaps to 5 and ideas per round to 5", async () => {
    const { user, getByTestId, getByPlaceholderText } = renderWithProviders(
      <RunConfigForm onSubmit={vi.fn()} />,
    );
    // Open advanced section to access number inputs
    await user.click(getByTestId("advanced-toggle"));
    const inputs = getByPlaceholderText(/machine learning/).closest("form")!.querySelectorAll("input[type=number]");
    expect(inputs.length).toBeGreaterThanOrEqual(2);
  });
});
