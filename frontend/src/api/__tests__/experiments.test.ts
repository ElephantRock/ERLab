import { beforeEach, describe, expect, it, vi } from "vitest";
import { listExperimentSpecs } from "@/api/experiments";
import { apiFetchJson } from "@/api/client";
import { ApiContractError } from "@/api/contracts/common";

vi.mock("@/api/client", () => ({
  apiFetchJson: vi.fn(),
  apiFetchVoid: vi.fn(),
}));

const mockApiFetchJson = vi.mocked(apiFetchJson);

describe("registered experiment catalog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("reads the registered-spec endpoint through the runtime contract", async () => {
    mockApiFetchJson.mockResolvedValue({
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
    });

    const result = await listExperimentSpecs();

    expect(mockApiFetchJson).toHaveBeenCalledWith(
      "/experiments/specs",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.compatible_strategies).toEqual(["academic_proposal", "deep_research"]);
    expect(result.specs[0]?.spec_id).toBe("phase5-pilot-v1");
  });

  it("fails closed when a material spec field is malformed", async () => {
    mockApiFetchJson.mockResolvedValue({
      compatible_strategies: ["deep_research"],
      specs: [
        {
          spec_id: "phase5-pilot-v1",
          description: "Iris pilot",
          research_question: "RQ",
          dataset_name: "iris",
          analysis_method: 42,
          primary_metric: "balanced_accuracy",
        },
      ],
    });

    await expect(listExperimentSpecs()).rejects.toBeInstanceOf(ApiContractError);
  });
});
