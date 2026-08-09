import { callContract } from "./contracts/common";
import { listExperimentSpecsContract } from "./contracts/experiments";
import type { ExperimentSpecCatalog } from "./types";

export function listExperimentSpecs(): Promise<ExperimentSpecCatalog> {
  return callContract(listExperimentSpecsContract);
}
