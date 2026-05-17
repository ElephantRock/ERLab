"""Synthesis scorer (paper and proposal).

Metrics: section_completeness, argument_coherence, citation_grounding,
         novelty_articulation, contradiction_handling, length_budget_adherence

NOTE: v0.2 structural checks are NOT sufficient for full production approval.
Paper/proposal synthesis is capped at limited_use unless manually overridden.
"""

from __future__ import annotations

from backend.pipeline.model_certification.stage_scorer import StageScorer
from backend.pipeline.model_certification.eval_case import StageEvalCase, GoldAnswer


class SynthesisScorer(StageScorer):
    stage = "synthesis"  # covers both paper_synthesis and proposal_synthesis

    def score(self, raw_output, parsed_output, case, gold=None):
        text = raw_output or ""
        word_count = len(text.split())

        # Section completeness: check for expected section headers
        expected_sections = []
        if gold and gold.expected_keys:
            expected_sections = gold.expected_keys
        else:
            expected_sections = ["introduction", "method", "result", "discussion", "conclusion"]

        text_lower = text.lower()
        found_sections = sum(1 for s in expected_sections if s in text_lower)
        section_completeness = found_sections / max(len(expected_sections), 1)

        # Argument coherence: check for transitional phrases (heuristic)
        coherence_markers = ["however", "therefore", "furthermore", "in contrast",
                             "consistent with", "supporting", "evidence suggests"]
        coherence_count = sum(1 for m in coherence_markers if m in text_lower)
        coherence = min(1.0, coherence_count / max(len(expected_sections), 1))

        # Citation grounding: citations per section
        citation_markers = ["[", "et al.", "(20", "doi:", "arxiv"]
        citation_count = sum(1 for m in citation_markers if m in text_lower)
        citation_grounding = min(1.0, citation_count / max(len(expected_sections) * 2, 1))

        # Novelty articulation: look for novelty/innovation keywords
        novelty_markers = ["novel", "contribution", "innovation", "first", "unique", "different"]
        novelty_count = sum(1 for m in novelty_markers if m in text_lower)
        novelty_articulation = min(1.0, novelty_count / 3)

        # Contradiction handling: look for acknowledgment of limitations
        contradiction_markers = ["limitation", "future work", "caveat", "does not",
                                "unresolved", "open question"]
        contradiction_handling = min(1.0, sum(1 for m in contradiction_markers if m in text_lower) / 2)

        # Length budget adherence
        budget = case.output_token_budget
        estimated_tokens = word_count * 1.3  # rough token estimate
        if estimated_tokens <= budget:
            length_adherence = 1.0
        elif estimated_tokens <= budget * 1.1:
            length_adherence = 0.8
        else:
            length_adherence = max(0.0, 1.0 - (estimated_tokens - budget) / budget)

        return {
            "section_completeness": round(section_completeness, 3),
            "argument_coherence": round(coherence, 3),
            "citation_grounding": round(citation_grounding, 3),
            "novelty_articulation": round(novelty_articulation, 3),
            "contradiction_handling": round(contradiction_handling, 3),
            "length_budget_adherence": round(length_adherence, 3),
        }

    def failures(self, raw_output, parsed_output, case, gold=None):
        scores = self.score(raw_output, parsed_output, case, gold)
        failures = []
        if scores["section_completeness"] < 0.5:
            failures.append("Low section completeness")
        if scores["length_budget_adherence"] < 0.5:
            failures.append("Length budget violated")
        if scores["citation_grounding"] < 0.3:
            failures.append("Low citation grounding")
        return failures
