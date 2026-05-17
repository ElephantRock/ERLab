"""Query generation scorer.

Metrics: query_relevance, query_diversity, duplicate_query_rate,
         malformed_query_rate, concept_coverage
"""

from __future__ import annotations

import json
import re
from typing import Any

from backend.pipeline.model_certification.stage_scorer import StageScorer
from backend.pipeline.model_certification.eval_case import StageEvalCase, GoldAnswer


class QueryGenerationScorer(StageScorer):
    stage = "query_generation"

    def score(self, raw_output, parsed_output, case, gold=None):
        queries = _extract_queries(raw_output, parsed_output)
        if not queries:
            return {
                "query_relevance": 0.0,
                "query_diversity": 0.0,
                "duplicate_query_rate": 1.0,
                "malformed_query_rate": 1.0,
                "concept_coverage": 0.0,
            }

        # Duplicate rate
        lowered = [q.lower().strip() for q in queries]
        unique = set(lowered)
        dup_rate = 1.0 - len(unique) / len(queries)

        # Malformed: queries that are empty or very short
        malformed = sum(1 for q in queries if len(q.strip()) < 5)
        malformed_rate = malformed / len(queries)

        # Diversity: ratio of unique first words
        first_words = set(q.split()[0].lower() for q in queries if q.split())
        diversity = min(1.0, len(first_words) / max(len(queries), 1))

        # Relevance: keyword overlap with gold expected keys
        relevance = 0.0
        if gold and gold.expected_keys:
            all_text = " ".join(queries).lower()
            matched = sum(1 for k in gold.expected_keys if k.lower() in all_text)
            relevance = matched / len(gold.expected_keys)
        elif gold and gold.expected_fields:
            all_text = " ".join(queries).lower()
            gold_terms = " ".join(str(v) for v in gold.expected_fields.values()).lower()
            gold_words = set(gold_terms.split())
            matched = sum(1 for w in gold_words if w in all_text)
            relevance = matched / max(len(gold_words), 1)
        else:
            relevance = 1.0 if not malformed else 0.5

        # Concept coverage: how many expected concepts appear
        coverage = relevance  # reuse for v0.2

        return {
            "query_relevance": round(relevance, 3),
            "query_diversity": round(diversity, 3),
            "duplicate_query_rate": round(dup_rate, 3),
            "malformed_query_rate": round(malformed_rate, 3),
            "concept_coverage": round(coverage, 3),
        }

    def failures(self, raw_output, parsed_output, case, gold=None):
        scores = self.score(raw_output, parsed_output, case, gold)
        failures = []
        if scores["malformed_query_rate"] > 0.5:
            failures.append("High malformed query rate")
        if scores["duplicate_query_rate"] > 0.5:
            failures.append("High duplicate query rate")
        if scores["query_relevance"] < 0.3:
            failures.append("Low query relevance to expected topics")
        return failures


def _extract_queries(raw_output, parsed_output):
    """Extract query list from output."""
    if parsed_output and "queries" in parsed_output:
        return parsed_output["queries"]
    if parsed_output and "query" in parsed_output:
        return [parsed_output["query"]]
    # Try parsing raw output as JSON
    try:
        data = json.loads(raw_output.strip())
        if isinstance(data, list):
            return [str(q) for q in data]
        if isinstance(data, dict):
            for key in ("queries", "query_list", "questions"):
                if key in data:
                    val = data[key]
                    if isinstance(val, list):
                        return [str(q) for q in val]
    except (json.JSONDecodeError, AttributeError):
        pass
    # Fallback: split by newlines
    lines = [l.strip().lstrip("0123456789.-) ") for l in raw_output.strip().split("\n") if l.strip()]
    return lines
