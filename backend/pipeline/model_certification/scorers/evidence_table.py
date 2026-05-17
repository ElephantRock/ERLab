"""Evidence table scorer.

Metrics: claim_to_paper_mapping_accuracy, unsupported_claim_rate,
         duplicate_evidence_rate, citation_completeness, consistency_score
"""

from __future__ import annotations

import json

from backend.pipeline.model_certification.stage_scorer import StageScorer
from backend.pipeline.model_certification.eval_case import StageEvalCase, GoldAnswer


class EvidenceTableScorer(StageScorer):
    stage = "evidence_table"

    def score(self, raw_output, parsed_output, case, gold=None):
        if parsed_output is None:
            return {k: 0.0 for k in (
                "claim_to_paper_mapping_accuracy", "unsupported_claim_rate",
                "duplicate_evidence_rate", "citation_completeness",
                "consistency_score",
            )}

        claims = parsed_output.get("claims", parsed_output.get("evidence", []))
        if not isinstance(claims, list):
            claims = []

        if not claims:
            return {k: 0.0 for k in (
                "claim_to_paper_mapping_accuracy", "unsupported_claim_rate",
                "duplicate_evidence_rate", "citation_completeness",
                "consistency_score",
            )}

        # Claim-to-paper mapping: how many claims have source citations
        mapped = sum(1 for c in claims if isinstance(c, dict) and c.get("source") or c.get("citation") or c.get("paper_id"))
        mapping_acc = mapped / len(claims)

        # Unsupported claim rate: claims without any backing
        unsupported = sum(1 for c in claims if isinstance(c, dict) and not c.get("evidence") and not c.get("support"))
        unsupported_rate = unsupported / len(claims)

        # Duplicate evidence: exact duplicates
        claim_texts = [str(c) if not isinstance(c, dict) else c.get("text", c.get("claim", str(c))) for c in claims]
        unique_claims = set(t.lower().strip() for t in claim_texts if t)
        dup_rate = 1.0 - len(unique_claims) / max(len(claim_texts), 1)

        # Citation completeness
        if gold and gold.expected_keys:
            gold_cites = set(gold.expected_keys)
            actual_cites = set()
            for c in claims:
                if isinstance(c, dict):
                    for key in ("citation", "source", "paper_id", "reference"):
                        if c.get(key):
                            actual_cites.add(str(c[key]).lower())
            cite_complete = len(gold_cites & actual_cites) / max(len(gold_cites), 1)
        else:
            cite_complete = 1.0 if mapped > 0 else 0.0

        # Consistency: no self-contradicting claims (heuristic)
        consistency = 1.0  # v0.2: assume consistent unless detected

        return {
            "claim_to_paper_mapping_accuracy": round(mapping_acc, 3),
            "unsupported_claim_rate": round(unsupported_rate, 3),
            "duplicate_evidence_rate": round(dup_rate, 3),
            "citation_completeness": round(cite_complete, 3),
            "consistency_score": round(consistency, 3),
        }

    def failures(self, raw_output, parsed_output, case, gold=None):
        scores = self.score(raw_output, parsed_output, case, gold)
        failures = []
        if scores["unsupported_claim_rate"] > 0.3:
            failures.append(f"High unsupported claim rate: {scores['unsupported_claim_rate']:.0%}")
        if scores["claim_to_paper_mapping_accuracy"] < 0.5:
            failures.append("Low claim-to-paper mapping")
        return failures
