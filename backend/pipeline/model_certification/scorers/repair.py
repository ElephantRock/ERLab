"""Repair scorer.

Metrics: json_repair_success, schema_repair_success, semantic_preservation,
         length_reduction_success, citation_field_normalization

Repair is a first-class capability — a model can be weak at synthesis
but valuable for repair.
"""

from __future__ import annotations

import json

from backend.pipeline.model_certification.stage_scorer import StageScorer
from backend.pipeline.model_certification.eval_case import StageEvalCase, GoldAnswer


class RepairScorer(StageScorer):
    stage = "repair"

    def score(self, raw_output, parsed_output, case, gold=None):
        text = (raw_output or "").strip()

        # JSON repair success: did the output become valid JSON?
        json_success = 0.0
        if parsed_output is not None:
            json_success = 1.0
        else:
            try:
                json.loads(text)
                json_success = 1.0
            except json.JSONDecodeError:
                pass

        # Schema repair success: does it match expected schema?
        schema_success = 0.0
        if json_success > 0 and gold and gold.expected_keys:
            try:
                data = parsed_output or json.loads(text)
                if isinstance(data, dict):
                    present = sum(1 for k in gold.expected_keys if k in data)
                    schema_success = present / len(gold.expected_keys)
                elif isinstance(data, list) and data:
                    schema_success = 0.5  # partial: list instead of dict
            except (json.JSONDecodeError, TypeError):
                pass
        elif json_success > 0:
            schema_success = 0.8  # No gold schema, but valid JSON

        # Semantic preservation: compare key content against gold
        semantic_pres = 0.0
        if gold and gold.expected_fields and json_success > 0:
            try:
                data = parsed_output or json.loads(text)
                if isinstance(data, dict):
                    gold_words = set(str(v).lower() for v in gold.expected_fields.values())
                    actual_words = set(str(v).lower() for v in data.values())
                    if gold_words:
                        overlap = len(gold_words & actual_words)
                        semantic_pres = overlap / len(gold_words)
                    else:
                        semantic_pres = 1.0
            except (json.JSONDecodeError, TypeError):
                pass
        elif json_success > 0:
            semantic_pres = 0.8  # assume ok without gold

        # Length reduction: repaired output should not be much longer
        input_text = case.input_context.get("broken_json", case.prompt_template)
        length_reduction = 0.5  # neutral
        if input_text and text:
            input_len = len(input_text)
            output_len = len(text)
            if output_len <= input_len * 1.2:
                length_reduction = 1.0
            elif output_len <= input_len * 1.5:
                length_reduction = 0.7

        # Citation field normalization: are citation fields clean?
        citation_norm = 0.5  # neutral
        if json_success > 0:
            try:
                data = parsed_output or json.loads(text)
                if isinstance(data, dict):
                    cite_fields = [v for k, v in data.items()
                                   if "cite" in k.lower() or "ref" in k.lower()]
                    if cite_fields:
                        clean = sum(1 for c in cite_fields
                                    if str(c).strip() and "[" in str(c) or "et al" in str(c).lower())
                        citation_norm = clean / max(len(cite_fields), 1)
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "json_repair_success": round(json_success, 3),
            "schema_repair_success": round(schema_success, 3),
            "semantic_preservation": round(semantic_pres, 3),
            "length_reduction_success": round(length_reduction, 3),
            "citation_field_normalization": round(citation_norm, 3),
        }

    def failures(self, raw_output, parsed_output, case, gold=None):
        scores = self.score(raw_output, parsed_output, case, gold)
        failures = []
        if scores["json_repair_success"] < 0.5:
            failures.append("JSON repair failed")
        if scores["semantic_preservation"] < 0.5:
            failures.append("Low semantic preservation after repair")
        return failures
