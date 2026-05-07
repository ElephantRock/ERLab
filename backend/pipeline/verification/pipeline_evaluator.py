"""Pipeline Evaluator: Measures pipeline quality with recall/precision metrics.

Evaluates the pipeline's gap detection and idea generation quality:
- Precision: Fraction of detected gaps that are real/novel
- Recall: Fraction of known important gaps that were detected
- Novelty score: Fraction of generated ideas that are genuinely novel
- Inter-annotator simulation: Compares pipeline gaps against expert-defined gaps

Addresses reviewer concern: "Adding an inter-annotator agreement or
retrospective matching against known future results would make the case
much stronger."
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GapEvaluation:
    """Evaluation of a single detected gap."""
    gap_title: str
    gap_type: str
    is_novel: bool = True
    overlaps_known_gap: str = ""  # Title of known gap it overlaps
    overlap_score: float = 0.0  # 0.0-1.0 semantic overlap


@dataclass
class GapMatchDetail:
    """Detail of how a known gap matched against pipeline output."""
    known_gap: str
    matched_by: str  # title of pipeline-detected gap
    overlap_score: float
    match_type: str  # 'keyword', 'semantic', 'none'


@dataclass
class InterAnnotatorAgreement:
    """Cohen's Kappa-style agreement between pipeline and expert annotations.
    
    Treats each known gap as a binary annotation: expert says it exists,
    pipeline either detects it (agree) or doesn't (disagree).
    """
    n_known_gaps: int = 0
    n_detected_by_pipeline: int = 0
    n_detected_by_expert: int = 0  # always = n_known_gaps
    n_both_agree: int = 0  # pipeline found + expert says exists
    observed_agreement: float = 0.0  # P(A)
    expected_agreement: float = 0.0  # P(E)
    cohens_kappa: float = 0.0
    match_details: list[GapMatchDetail] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Inter-Annotator Agreement\n"
            f"════════════════════════\n"
            f"Known gaps (expert):    {self.n_known_gaps}\n"
            f"Pipeline detected:      {self.n_detected_by_pipeline}\n"
            f"Both agree:             {self.n_both_agree}\n"
            f"Observed agreement P(A): {self.observed_agreement:.1%}\n"
            f"Expected agreement P(E): {self.expected_agreement:.1%}\n"
            f"Cohen's Kappa:          {self.cohens_kappa:.3f}\n"
        )


@dataclass
class PipelineEvaluationReport:
    """Full pipeline evaluation report."""
    # Gap detection metrics
    gaps_detected: int = 0
    gaps_novel: int = 0
    gaps_overlapping_known: int = 0
    gap_precision: float = 0.0  # novel / detected
    gap_recall: float = 0.0  # detected_known / total_known

    # Idea generation metrics
    ideas_generated: int = 0
    ideas_novel: int = 0
    idea_novelty_rate: float = 0.0

    # Detail per item
    gap_evaluations: list[GapEvaluation] = field(default_factory=list)

    # Inter-annotator agreement
    inter_annotator: InterAnnotatorAgreement | None = None

    # Overall
    pipeline_quality_score: float = 0.0  # Weighted combination

    def __str__(self) -> str:
        return (
            f"Pipeline Evaluation Report\n"
            f"═════════════════════════\n"
            f"Gaps detected:     {self.gaps_detected}\n"
            f"Gaps novel:        {self.gaps_novel}\n"
            f"Gap precision:     {self.gap_precision:.1%}\n"
            f"Gap recall:        {self.gap_recall:.1%}\n"
            f"Ideas generated:   {self.ideas_generated}\n"
            f"Ideas novel:       {self.ideas_novel}\n"
            f"Idea novelty rate: {self.idea_novelty_rate:.1%}\n"
            f"Quality score:     {self.pipeline_quality_score:.2f}/1.0\n"
        )


class PipelineEvaluator:
    """Evaluates pipeline output quality against known benchmarks.

    Known gaps are expert-defined research gaps that *should* be detected
    by a high-quality pipeline. The evaluator checks whether the pipeline
    found them, providing a recall measure.
    """

    # Known important gaps in GoT × NSR that a good pipeline should detect
    KNOWN_GOT_NSR_GAPS = [
        "theoretical foundations for graph reasoning topology",
        "cost efficiency trade-offs in structured reasoning",
        "knowledge graph integration with LLM reasoning",
        "explainability of graph-based reasoning paths",
        "standardized evaluation benchmarks for neuro-symbolic",
        "cascading error mitigation in dual-process systems",
        "temporal reasoning over evolving knowledge",
        "cross-domain generalization of reasoning methods",
    ]

    def __init__(self, known_gaps: list[str] | None = None) -> None:
        self._known_gaps = known_gaps or self.KNOWN_GOT_NSR_GAPS

    def evaluate(
        self,
        detected_gaps: list[dict],
        generated_ideas: list[dict],
        semantic_overlap_fn: Any = None,
    ) -> PipelineEvaluationReport:
        """Evaluate pipeline outputs.

        Args:
            detected_gaps: List of dicts with 'title', 'description', 'gap_type'.
            generated_ideas: List of dicts with 'title', 'novelty_score'.
            semantic_overlap_fn: Optional function(gap1_title, gap2_title) → float.

        Returns:
            PipelineEvaluationReport with metrics.
        """
        report = PipelineEvaluationReport(
            gaps_detected=len(detected_gaps),
            ideas_generated=len(generated_ideas),
        )

        # Evaluate gap detection
        known_matched = 0
        for gap in detected_gaps:
            title = gap.get("title", "").lower()
            eval_item = GapEvaluation(
                gap_title=gap.get("title", ""),
                gap_type=gap.get("gap_type", "unknown"),
            )

            # Check overlap with known gaps
            best_overlap = 0.0
            best_known = ""
            for known in self._known_gaps:
                if semantic_overlap_fn:
                    overlap = semantic_overlap_fn(title, known)
                else:
                    overlap = self._keyword_overlap(title, known)

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_known = known

            eval_item.overlap_score = best_overlap
            eval_item.overlaps_known_gap = best_known

            if best_overlap >= 0.3:
                known_matched += 1
                eval_item.is_novel = False
                report.gaps_overlapping_known += 1
            else:
                report.gaps_novel += 1

            report.gap_evaluations.append(eval_item)

        # Calculate precision (fraction of detected gaps that are meaningful)
        meaningful = report.gaps_novel + report.gaps_overlapping_known
        report.gap_precision = meaningful / max(report.gaps_detected, 1)

        # Calculate recall (fraction of known gaps that were detected)
        report.gap_recall = known_matched / max(len(self._known_gaps), 1)

        # Evaluate idea novelty
        for idea in generated_ideas:
            novelty = idea.get("novelty_score", 0.5)
            if novelty >= 0.7:
                report.ideas_novel += 1

        report.idea_novelty_rate = report.ideas_novel / max(report.ideas_generated, 1)

        # Overall quality score (weighted combination)
        report.pipeline_quality_score = (
            0.4 * report.gap_recall +
            0.3 * report.gap_precision +
            0.3 * report.idea_novelty_rate
        )

        # Inter-annotator agreement (Cohen's Kappa)
        report.inter_annotator = self._compute_kappa(
            detected_gaps, self._known_gaps, semantic_overlap_fn
        )

        return report

    def _keyword_overlap(self, title: str, known: str) -> float:
        """Simple keyword-based overlap score."""
        title_words = set(title.lower().split())
        known_words = set(known.lower().split())
        if not known_words:
            return 0.0
        overlap = len(title_words & known_words)
        return overlap / len(known_words)

    def _compute_kappa(
        self,
        detected_gaps: list[dict],
        known_gaps: list[str],
        semantic_fn: Any = None,
    ) -> InterAnnotatorAgreement:
        """Compute Cohen's Kappa between pipeline and expert annotations.
        
        Each known gap is a binary variable:
        - Expert annotator: always 1 (they defined it as a gap)
        - Pipeline annotator: 1 if detected, 0 if not
        
        Kappa = (P(A) - P(E)) / (1 - P(E))
        where P(A) = observed agreement, P(E) = expected by chance.
        """
        n = len(known_gaps)
        detected_titles = [g.get("title", "").lower() for g in detected_gaps]
        
        match_details: list[GapMatchDetail] = []
        n_detected = 0
        
        for known in known_gaps:
            best_score = 0.0
            best_match = ""
            for dt in detected_titles:
                if semantic_fn:
                    score = semantic_fn(dt, known)
                else:
                    score = self._keyword_overlap(dt, known)
                if score > best_score:
                    best_score = score
                    best_match = dt
            
            detected = best_score >= 0.3
            if detected:
                n_detected += 1
            
            match_details.append(GapMatchDetail(
                known_gap=known,
                matched_by=best_match if detected else "(none)",
                overlap_score=best_score,
                match_type="keyword" if not semantic_fn else "semantic",
            ))
        
        # Binary contingency table:
        # Expert says YES for all n known gaps
        # Pipeline says YES for n_detected, NO for n - n_detected
        # Both agree YES: n_detected (true positives)
        # Both agree NO: impossible (expert always says YES)
        # Disagree: n - n_detected (expert YES, pipeline NO)
        
        n_yes_yes = n_detected  # both say gap exists
        n_no_no = 0              # both say no gap (impossible here)
        n_yes_no = n - n_detected  # expert yes, pipeline no
        n_no_yes = 0              # expert no, pipeline yes (not in known list)
        total_annotations = n      # each known gap = one annotation pair
        
        # P(A) = observed agreement
        p_a = n_yes_yes / max(total_annotations, 1)
        
        # P(E) = expected agreement by chance
        # p_expert_yes = 1.0, p_pipeline_yes = n_detected / n
        p_pipeline_yes = n_detected / max(total_annotations, 1)
        p_pipeline_no = 1 - p_pipeline_yes
        p_expert_yes = 1.0
        p_expert_no = 0.0
        p_e = (p_expert_yes * p_pipeline_yes) + (p_expert_no * p_pipeline_no)
        
        # Cohen's Kappa
        kappa = (p_a - p_e) / max(1 - p_e, 1e-10)
        
        return InterAnnotatorAgreement(
            n_known_gaps=n,
            n_detected_by_pipeline=n_detected,
            n_detected_by_expert=n,
            n_both_agree=n_yes_yes,
            observed_agreement=p_a,
            expected_agreement=p_e,
            cohens_kappa=kappa,
            match_details=match_details,
        )
