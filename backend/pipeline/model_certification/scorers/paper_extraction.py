"""Paper extraction scorer.

Metrics: field_completeness, factual_extraction_accuracy,
         method_extraction_accuracy, result_extraction_accuracy,
         limitation_extraction_accuracy, citation_alignment
"""

from __future__ import annotations

from backend.pipeline.model_certification.stage_scorer import StageScorer


class PaperExtractionScorer(StageScorer):
    stage = "paper_extraction"

    def score(self, raw_output, parsed_output, case, gold=None):
        if parsed_output is None:
            return {k: 0.0 for k in (
                "field_completeness", "factual_extraction_accuracy",
                "method_extraction_accuracy", "result_extraction_accuracy",
                "limitation_extraction_accuracy", "citation_alignment",
            )}

        # Field completeness
        if gold and gold.expected_keys:
            present = sum(1 for k in gold.expected_keys if k in parsed_output)
            completeness = present / len(gold.expected_keys)
        else:
            # Default expected fields for paper extraction
            default_fields = {"title", "abstract", "authors", "year", "method", "results"}
            present = sum(1 for f in default_fields if f in parsed_output)
            completeness = present / len(default_fields)

        # Sub-field accuracy against gold
        method_acc = _field_accuracy(parsed_output, gold, "method")
        result_acc = _field_accuracy(parsed_output, gold, "results")
        limitation_acc = _field_accuracy(parsed_output, gold, "limitations")
        citation_acc = _field_accuracy(parsed_output, gold, "citations")

        # Overall factual accuracy
        factual_acc = (method_acc + result_acc + limitation_acc + citation_acc) / 4

        return {
            "field_completeness": round(completeness, 3),
            "factual_extraction_accuracy": round(factual_acc, 3),
            "method_extraction_accuracy": round(method_acc, 3),
            "result_extraction_accuracy": round(result_acc, 3),
            "limitation_extraction_accuracy": round(limitation_acc, 3),
            "citation_alignment": round(citation_acc, 3),
        }

    def failures(self, raw_output, parsed_output, case, gold=None):
        scores = self.score(raw_output, parsed_output, case, gold)
        failures = []
        if scores["field_completeness"] < 0.5:
            failures.append(f"Low field completeness: {scores['field_completeness']:.0%}")
        if scores["factual_extraction_accuracy"] < 0.5:
            failures.append("Low factual extraction accuracy")
        return failures


def _field_accuracy(parsed, gold, field_name):
    """Compare a field value against gold using keyword overlap."""
    if gold is None or field_name not in gold.expected_fields:
        return 1.0  # No gold to compare against, assume ok

    gold_val = str(gold.expected_fields[field_name]).lower()
    gold_words = set(gold_val.split())

    if field_name not in parsed:
        return 0.0

    actual_val = str(parsed[field_name]).lower()
    actual_words = set(actual_val.split())

    if not gold_words:
        return 1.0

    overlap = len(gold_words & actual_words)
    return overlap / len(gold_words)
