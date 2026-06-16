"""Feasibility scoring — evaluate practical viability of research ideas."""

import logging

from backend.pipeline.generation.models import ResearchIdea
from backend.pipeline.novelty.novelty_checker import NoveltyReport
from backend.providers.base import LLMProvider

logger = logging.getLogger(__name__)

FEASIBILITY_PROMPT = """You are a research feasibility evaluator. Assess the practical viability of this research idea.

## Research Idea:
Title: {title}
Problem: {problem}
Method: {method}
Contributions: {contributions}
Evaluation: {evaluation}

## Novelty Assessment:
Overall novelty: {novelty_score:.2f}
{novelty_arguments}

Score each dimension from 0 to 10:
1. **data_availability** (0-10): Are the required datasets publicly available or obtainable?
2. **computational_requirements** (0-10): Can this be done with reasonable compute (1-4 GPUs for <1 month)?
3. **methodological_complexity** (0-10): Can the methods be implemented in ~3 months by a small team?
4. **evaluation_plan** (0-10): Are the baselines and metrics well-defined and achievable?
5. **novelty_grounding** (0-10): Is the novelty claim defensible against existing work?
6. **impact_potential** (0-10): Expected citation potential and community interest?

Also provide:
- **overall_score**: Weighted average (data 20%, compute 15%, methods 20%, eval 20%, novelty 10%, impact 15%)
- **reasoning**: A paragraph explaining the scores
- **estimated_timeline**: Realistic timeline estimate (e.g., "3-6 months")
- **key_risks**: Top 2-3 risks that could prevent success"""


class FeasibilityReport:
    def __init__(
        self,
        overall_score: float,
        data_availability: float,
        computational_requirements: float,
        methodological_complexity: float,
        evaluation_plan: float,
        novelty_grounding: float,
        impact_potential: float,
        reasoning: str,
        estimated_timeline: str,
        key_risks: list[str],
        counterfactual_analysis: dict | None = None,
        sensitivity_scores: dict | None = None,
        refutation_passed: bool | None = None,
    ):
        self.overall_score = overall_score
        self.data_availability = data_availability
        self.computational_requirements = computational_requirements
        self.methodological_complexity = methodological_complexity
        self.evaluation_plan = evaluation_plan
        self.novelty_grounding = novelty_grounding
        self.impact_potential = impact_potential
        self.reasoning = reasoning
        self.estimated_timeline = estimated_timeline
        self.key_risks = key_risks
        self.counterfactual_analysis = counterfactual_analysis
        self.sensitivity_scores = sensitivity_scores
        self.refutation_passed = refutation_passed


class FeasibilityScorer:
    def __init__(self, provider: LLMProvider):
        self._provider = provider

    async def score_feasibility(
        self,
        idea: ResearchIdea,
        novelty_report: NoveltyReport | None = None,
        weight_overrides: dict[str, float] | None = None,
        *,
        provider: LLMProvider | None = None,
        receipts: list | None = None,
    ) -> FeasibilityReport:
        """Evaluate idea feasibility across 6 dimensions.

        Args:
            weight_overrides: Optional dict to override default dimension weights
                for computing the composite overall_score. Keys: data, compute,
                methods, eval, novelty, impact.
        """
        prompt = FEASIBILITY_PROMPT.format(
            title=idea.title,
            problem=idea.problem_statement,
            method=idea.proposed_method,
            contributions=idea.expected_contributions,
            evaluation=idea.evaluation_approach,
            novelty_score=novelty_report.overall_score if novelty_report else 0.5,
            novelty_arguments=novelty_report.novelty_arguments
            if novelty_report
            else "Not assessed",
        )

        try:
            llm = provider or self._provider
            # Collect receipt for this model-backed call
            if receipts is not None:
                from backend.pipeline.operations.provider_conformance import build_receipt_from_provider
                receipts.append(build_receipt_from_provider(llm))
            result = await llm.structured_output(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert research feasibility evaluator for AI/NLP projects.",
                    },
                    {"role": "user", "content": prompt},
                ],
                schema={
                    "type": "object",
                    "properties": {
                        "data_availability": {"type": "number"},
                        "computational_requirements": {"type": "number"},
                        "methodological_complexity": {"type": "number"},
                        "evaluation_plan": {"type": "number"},
                        "novelty_grounding": {"type": "number"},
                        "impact_potential": {"type": "number"},
                        "overall_score": {"type": "number"},
                        "reasoning": {"type": "string"},
                        "estimated_timeline": {"type": "string"},
                        "key_risks": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["overall_score", "reasoning"],
                },
                temperature=0.2,
            )

            data = min(10, max(0, result.get("data_availability", 5.0)))
            compute = min(10, max(0, result.get("computational_requirements", 5.0)))
            methods = min(10, max(0, result.get("methodological_complexity", 5.0)))
            eval_plan = min(10, max(0, result.get("evaluation_plan", 5.0)))
            novelty_grounding = min(10, max(0, result.get("novelty_grounding", 5.0)))
            impact = min(10, max(0, result.get("impact_potential", 5.0)))

            # Compute composite score with optional weight overrides
            base_weights = {
                "data": 0.20, "compute": 0.15, "methods": 0.20,
                "eval": 0.20, "novelty": 0.10, "impact": 0.15,
            }
            if weight_overrides:
                base_weights.update(weight_overrides)
                # Normalize to sum=1.0
                total = sum(base_weights.values())
                if total > 0:
                    base_weights = {k: v / total for k, v in base_weights.items()}

            composite = (
                (data / 10.0) * base_weights["data"]
                + (compute / 10.0) * base_weights["compute"]
                + (methods / 10.0) * base_weights["methods"]
                + (eval_plan / 10.0) * base_weights["eval"]
                + (novelty_grounding / 10.0) * base_weights["novelty"]
                + (impact / 10.0) * base_weights["impact"]
            ) * 10.0

            return FeasibilityReport(
                overall_score=round(composite, 1),
                data_availability=data,
                computational_requirements=compute,
                methodological_complexity=methods,
                evaluation_plan=eval_plan,
                novelty_grounding=novelty_grounding,
                impact_potential=impact,
                reasoning=result.get("reasoning", ""),
                estimated_timeline=result.get("estimated_timeline", "Unknown"),
                key_risks=result.get("key_risks", []),
            )

        except Exception as e:
            logger.error("Feasibility scoring failed: %s", e)
            return FeasibilityReport(
                overall_score=5.0,
                data_availability=5.0,
                computational_requirements=5.0,
                methodological_complexity=5.0,
                evaluation_plan=5.0,
                novelty_grounding=5.0,
                impact_potential=5.0,
                reasoning=f"Scoring failed: {e}",
                estimated_timeline="Unknown",
                key_risks=["Scoring evaluation failed"],
            )

    async def run_counterfactual(self, report: FeasibilityReport) -> FeasibilityReport:
        """Run counterfactual analysis on a scored feasibility report.

        Adds counterfactual_analysis, sensitivity_scores, and refutation_passed
        to the report. Returns a new report with these fields populated.
        """
        try:
            from backend.pipeline.feasibility.causal_dag import PipelineCausalModel

            model = PipelineCausalModel()
            scores = model.feasibility_to_dag_scores(report)

            # Counterfactual for each key dimension
            counterfactuals = {}
            for dim in ["data_availability", "method_feasibility", "idea_novelty"]:
                original = scores.get(dim, 5.0)
                cf_high = model.counterfactual(scores, dim, min(10.0, original + 2.0))
                cf_low = model.counterfactual(scores, dim, max(0.0, original - 2.0))
                counterfactuals[dim] = {
                    "original": original,
                    "if_plus_2": {
                        "predicted_impact": round(cf_high.predicted_impact, 3),
                        "new_impact_score": round(cf_high.new_scores.get("impact_potential", original), 2),
                    },
                    "if_minus_2": {
                        "predicted_impact": round(cf_low.predicted_impact, 3),
                        "new_impact_score": round(cf_low.new_scores.get("impact_potential", original), 2),
                    },
                }

            # Sensitivity analysis
            sensitivity = model.sensitivity_analysis(scores)
            sensitivity_scores = {
                dim: score for dim, score in sensitivity.dimension_rankings
            }

            # Refutation tests
            refutation = model.run_refutation_tests(scores)

            return FeasibilityReport(
                overall_score=report.overall_score,
                data_availability=report.data_availability,
                computational_requirements=report.computational_requirements,
                methodological_complexity=report.methodological_complexity,
                evaluation_plan=report.evaluation_plan,
                novelty_grounding=report.novelty_grounding,
                impact_potential=report.impact_potential,
                reasoning=report.reasoning,
                estimated_timeline=report.estimated_timeline,
                key_risks=report.key_risks,
                counterfactual_analysis=counterfactuals,
                sensitivity_scores=sensitivity_scores,
                refutation_passed=refutation.all_passed,
            )
        except Exception as e:
            logger.warning("Counterfactual analysis failed: %s", e)
            return report
