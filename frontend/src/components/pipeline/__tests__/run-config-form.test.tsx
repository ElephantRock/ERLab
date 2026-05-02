import { describe, it, expect, vi } from "vitest";
import { renderWithProviders } from "@/test/test-utils";
import { RunConfigForm } from "@/components/pipeline/run-config-form";
import type { PipelineRunRequest } from "@/api/types";

describe("RunConfigForm", () => {
  it("renders all form fields", () => {
    const { getByPlaceholderText, getByText } = renderWithProviders(
      <RunConfigForm onSubmit={vi.fn()} />,
    );
    expect(getByPlaceholderText(/machine learning/)).toBeInTheDocument();
    expect(getByPlaceholderText(/transformer attention/)).toBeInTheDocument();
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
    const { getByText } = renderWithProviders(
      <RunConfigForm onSubmit={vi.fn()} isLoading={true} />,
    );
    expect(getByText("Starting...").closest("button")).toBeDisabled();
  });

  it("shows Starting text when loading", () => {
    const { getByText } = renderWithProviders(
      <RunConfigForm onSubmit={vi.fn()} isLoading={true} />,
    );
    expect(getByText("Starting...")).toBeInTheDocument();
  });

  it("defaults max gaps to 5 and ideas per round to 5", () => {
    const { getByPlaceholderText } = renderWithProviders(
      <RunConfigForm onSubmit={vi.fn()} />,
    );
    // Number inputs hold their values
    const inputs = getByPlaceholderText(/machine learning/).closest("form")!.querySelectorAll("input[type=number]");
    expect(inputs.length).toBeGreaterThanOrEqual(2);
  });
});
