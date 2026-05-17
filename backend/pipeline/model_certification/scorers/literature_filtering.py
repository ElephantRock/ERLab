"""Literature filtering scorer.

Metrics: precision, recall, false_rejection_rate, false_inclusion_rate, ranking_quality
Recall is weighted more than precision — false rejection is more dangerous.
"""

from __future__ import annotations

import json

from backend.pipeline.model_certification.stage_scorer import StageScorer
from backend.pipeline.model_certification.eval_case import StageEvalCase, GoldAnswer


class LiteratureFilteringScorer(StageScorer):
    stage = "literature_filtering"

    def score(self, raw_output, parsed_output, case, gold=None):
        included = _extract_ids(raw_output, parsed_output)
        gold_incl = set(gold.inclusion_set) if gold and gold.inclusion_set else set()
        gold_excl = set(gold.exclusion_set) if gold and gold.exclusion_set else set()

        if not gold_incl and not gold_excl:
            return {
                "precision": 1.0, "recall": 1.0,
                "false_rejection_rate": 0.0, "false_inclusion_rate": 0.0,
                "ranking_quality": 1.0,
            }

        included_set = set(included)

        # True positives: in gold inclusion AND in result
        tp = len(gold_incl & included_set)
        # False negatives: in gold inclusion but NOT in result
        fn = len(gold_incl - included_set)
        # False positives: in result but NOT in gold inclusion
        fp = len(included_set - gold_incl)
        # True negatives: in gold exclusion AND not in result
        tn = len(gold_excl - included_set)

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)

        # Weighted score: recall matters more (1.5x) than precision
        false_rejection_rate = fn / max(len(gold_incl), 1)
        false_inclusion_rate = fp / max(len(included_set), 1)

        # Ranking quality: are gold papers ranked higher?
        ranking_quality = _compute_ranking_quality(included, gold_incl)

        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "false_rejection_rate": round(false_rejection_rate, 3),
            "false_inclusion_rate": round(false_inclusion_rate, 3),
            "ranking_quality": round(ranking_quality, 3),
        }

    def failures(self, raw_output, parsed_output, case, gold=None):
        scores = self.score(raw_output, parsed_output, case, gold)
        failures = []
        if scores["false_rejection_rate"] > 0.3:
            failures.append(f"High false rejection: {scores['false_rejection_rate']:.0%}")
        if scores["recall"] < 0.5:
            failures.append(f"Low recall: {scores['recall']:.0%}")
        return failures


def _extract_ids(raw_output, parsed_output):
    """Extract paper IDs from output."""
    if parsed_output:
        if "included_ids" in parsed_output:
            return [str(x) for x in parsed_output["included_ids"]]
        if "ids" in parsed_output:
            return [str(x) for x in parsed_output["ids"]]
        if "papers" in parsed_output:
            papers = parsed_output["papers"]
            if isinstance(papers, list):
                return [str(p.get("id", p)) if isinstance(p, dict) else str(p) for p in papers]
    try:
        data = json.loads(raw_output.strip())
        if isinstance(data, list):
            return [str(x) for x in data]
    except (json.JSONDecodeError, AttributeError):
        pass
    return []


def _compute_ranking_quality(included, gold_incl):
    """Check if gold papers appear early in the ranking."""
    if not included or not gold_incl:
        return 1.0
    gold_positions = []
    for gid in gold_incl:
        if gid in included:
            idx = included.index(gid)
            gold_positions.append(idx)
    if not gold_positions:
        return 0.0
    avg_pos = sum(gold_positions) / len(gold_positions)
    # Normalize: perfect = 1.0, worst = 0.0
    return max(0.0, 1.0 - avg_pos / max(len(included), 1))
