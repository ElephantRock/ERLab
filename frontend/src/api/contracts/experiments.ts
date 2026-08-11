/** Runtime contract for registered empirical experiment specifications. */

import {
  decodeArray,
  decodeObject,
  decodeString,
  type JsonContract,
} from "./common";
import type { ExperimentSpecCatalog, ExperimentSpecSummary } from "@/api/types";

const experimentSpecDecoder = decodeObject<ExperimentSpecSummary>({
  required: {
    spec_id: decodeString,
    description: decodeString,
    research_question: decodeString,
    dataset_name: decodeString,
    analysis_method: decodeString,
    primary_metric: decodeString,
  },
});

const experimentSpecCatalogDecoder = decodeObject<ExperimentSpecCatalog>({
  required: {
    specs: decodeArray(experimentSpecDecoder),
    compatible_strategies: decodeArray(decodeString),
  },
});

export const listExperimentSpecsContract: JsonContract<ExperimentSpecCatalog> = {
  id: "experiments.listSpecs",
  method: "GET",
  pathPattern: "/experiments/specs",
  responseKind: "json",
  decoder: experimentSpecCatalogDecoder,
};
