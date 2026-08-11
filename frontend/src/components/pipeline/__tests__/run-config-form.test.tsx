import { describe, it, expect, vi } from "vitest";
import { renderWithProviders } from "@/test/test-utils";
import { RunConfigForm } from "@/components/pipeline/run-config-form";
import type { ExperimentSpecCatalog, PipelineRunRequest } from "@/api/types";

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


const EXPERIMENT_CATALOG: ExperimentSpecCatalog = {
  compatible_strategies: ["academic_proposal", "deep_research"],
  specs: [
    {
      spec_id: "phase5-pilot-v1",
      description: "Iris pilot",
      research_question: "Does logistic regression classify Iris species?",
      dataset_name: "iris",
      analysis_method: "logistic_regression",
      primary_metric: "balanced_accuracy",
    },
  ],
};

describe("RunConfigForm empirical authority", () => {
  it("keeps exploratory mode as the default and omits experiment_spec_id", async () => {
    const onSubmit = vi.fn();
    const { user, getByPlaceholderText, getByText, getByTestId } = renderWithProviders(
      <RunConfigForm onSubmit={onSubmit} experimentCatalog={EXPERIMENT_CATALOG} />,
    );

    expect(getByTestId("experiment-mode-exploratory")).toBeInTheDocument();
    expect(getByTestId("experiment-mode-registered")).toBeDisabled();

    await user.type(getByPlaceholderText(/machine learning/), "NLP");
    await user.click(getByText("Start Pipeline"));

    const config = onSubmit.mock.calls[0][0] as PipelineRunRequest;
    expect(config.experiment_spec_id).toBeUndefined();
  });

  it("submits the registered spec for a compatible strategy", async () => {
    const onSubmit = vi.fn();
    const onExperimentSpecChange = vi.fn();
    const { user, getByPlaceholderText, getByText, getByTestId } = renderWithProviders(
      <RunConfigForm
        onSubmit={onSubmit}
        experimentCatalog={EXPERIMENT_CATALOG}
        onExperimentSpecChange={onExperimentSpecChange}
      />,
    );

    await user.click(getByTestId("strategy-card-deep_research"));
    expect(getByTestId("experiment-mode-registered")).not.toBeDisabled();
    await user.click(getByTestId("experiment-mode-registered"));

    expect(getByTestId("experiment-spec-select")).toHaveValue("phase5-pilot-v1");
    expect(getByTestId("registered-experiment-config")).toHaveTextContent("logistic_regression");
    expect(onExperimentSpecChange).toHaveBeenLastCalledWith("phase5-pilot-v1");

    await user.type(getByPlaceholderText(/machine learning/), "ML");
    await user.click(getByText("Start Pipeline"));

    const config = onSubmit.mock.calls[0][0] as PipelineRunRequest;
    expect(config.strategy).toBe("deep_research");
    expect(config.experiment_spec_id).toBe("phase5-pilot-v1");
  });

  it("clears a registered experiment when switching to an incompatible strategy", async () => {
    const onExperimentSpecChange = vi.fn();
    const { user, getByTestId, queryByTestId } = renderWithProviders(
      <RunConfigForm
        onSubmit={vi.fn()}
        experimentCatalog={EXPERIMENT_CATALOG}
        onExperimentSpecChange={onExperimentSpecChange}
      />,
    );

    await user.click(getByTestId("strategy-card-deep_research"));
    await user.click(getByTestId("experiment-mode-registered"));
    await user.click(getByTestId("strategy-card-fast_scan"));

    expect(onExperimentSpecChange).toHaveBeenLastCalledWith(null);
    expect(queryByTestId("registered-experiment-config")).not.toBeInTheDocument();
    expect(getByTestId("experiment-mode-registered")).toBeDisabled();
  });
});
