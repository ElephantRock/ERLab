"""Evaluation Plan Generator: Produces concrete evaluation criteria for proposals.

Takes a proposal's method section and generates:
1. Recommended datasets (name, size, availability)
2. Baseline methods (name, citation, description)
3. Metrics with formulas and targets
4. Ablation experiment designs

Addresses reviewer concern: "What would constitute a successful implementation?"
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DatasetRecommendation:
    """A recommended dataset for evaluation."""
    name: str
    size: str
    availability: str
    relevance: str = ""


@dataclass
class BaselineMethod:
    """A baseline method for comparison."""
    name: str
    citation: str
    description: str


@dataclass
class MetricTarget:
    """A metric with target value and baseline."""
    name: str
    formula: str
    target: float
    baseline: float
    unit: str = ""


@dataclass
class AblationExperiment:
    """An ablation experiment design."""
    name: str
    description: str
    what_to_remove: str
    expected_impact: str


@dataclass
class EvaluationPlan:
    """Complete evaluation plan for a proposal."""
    idea_id: int
    title: str
    datasets: list[DatasetRecommendation] = field(default_factory=list)
    baselines: list[BaselineMethod] = field(default_factory=list)
    metrics: list[MetricTarget] = field(default_factory=list)
    ablations: list[AblationExperiment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "idea_id": self.idea_id,
            "title": self.title,
            "datasets": [{"name": d.name, "size": d.size, "availability": d.availability}
                         for d in self.datasets],
            "baselines": [{"name": b.name, "citation": b.citation, "description": b.description}
                          for b in self.baselines],
            "metrics": [{"name": m.name, "formula": m.formula, "target": m.target,
                         "baseline": m.baseline, "unit": m.unit}
                        for m in self.metrics],
            "ablations": [{"name": a.name, "description": a.description,
                           "what_to_remove": a.what_to_remove, "expected_impact": a.expected_impact}
                          for a in self.ablations],
        }


class EvaluationPlanGenerator:
    """Generates structured evaluation plans for research proposals.

    In template mode (no LLM), produces a default plan structure.
    In LLM mode, uses the provider to generate domain-specific plans.
    """

    def __init__(self, provider: Any = None) -> None:
        self._provider = provider

    async def generate(self, idea: dict) -> EvaluationPlan:
        """Generate an evaluation plan for a proposal.

        Args:
            idea: Dict with 'id', 'title', 'proposed_method'.

        Returns:
            EvaluationPlan with datasets, baselines, metrics, ablations.
        """
        if self._provider:
            try:
                return await self._generate_with_llm(idea)
            except Exception as e:
                logger.warning("LLM plan generation failed for idea %s: %s", idea.get("id"), e)
                return self._generate_template(idea)
        return self._generate_template(idea)

    async def _generate_with_llm(self, idea: dict) -> EvaluationPlan:
        """Use LLM to generate evaluation plan."""
        prompt = (
            f"Generate a detailed evaluation plan for this research proposal:\n\n"
            f"Title: {idea.get('title', '')}\n"
            f"Method: {idea.get('proposed_method', '')}\n\n"
            f"Provide:\n"
            f"1. 3 recommended datasets with name, size, and availability\n"
            f"2. 3 baseline methods with name, citation, and description\n"
            f"3. 4 metrics with formula, target value (0-1), and baseline value\n"
            f"4. 3 ablation experiments\n\n"
            f"Respond in JSON format."
        )
        result = await self._provider.complete(prompt)
        return self._parse_llm_plan(idea, result)

    def _generate_template(self, idea: dict) -> EvaluationPlan:
        """Generate a structured template plan (no LLM needed)."""
        title = idea.get("title", "Untitled")
        idea_id = idea.get("id", 0)

        datasets = [
            DatasetRecommendation(
                name="Standard Benchmark Suite",
                size="10K-100K samples",
                availability="Public (GitHub/HuggingFace)",
                relevance=f"Standard evaluation for {title}",
            ),
            DatasetRecommendation(
                name="Domain-Specific Corpus",
                size="1K-10K samples",
                availability="Public (paperswithcode.com)",
                relevance="Domain-specific reasoning tasks",
            ),
            DatasetRecommendation(
                name="Synthetic Stress Test",
                size="1K samples (generated)",
                availability="Self-generated",
                relevance="Edge cases and adversarial inputs",
            ),
        ]

        baselines = [
            BaselineMethod(
                name="Chain-of-Thought (CoT)",
                citation="Wei et al., 2022",
                description="Standard prompting with step-by-step reasoning",
            ),
            BaselineMethod(
                name="Few-Shot In-Context Learning",
                citation="Brown et al., 2020",
                description="Provide k examples in context without fine-tuning",
            ),
            BaselineMethod(
                name="Fine-tuned Domain Model",
                citation="Domain-specific",
                description="Model fine-tuned on task-specific training data",
            ),
        ]

        metrics = [
            MetricTarget(
                name="Accuracy",
                formula="correct / total",
                target=0.85,
                baseline=0.72,
                unit="fraction",
            ),
            MetricTarget(
                name="F1 Score",
                formula="2 * (precision * recall) / (precision + recall)",
                target=0.80,
                baseline=0.65,
                unit="fraction",
            ),
            MetricTarget(
                name="Latency",
                formula="time_end - time_start",
                target=5.0,
                baseline=3.0,
                unit="seconds",
            ),
            MetricTarget(
                name="Cost Efficiency",
                formula="accuracy / (cost_per_1k_tokens)",
                target=0.01,
                baseline=0.004,
                unit="accuracy/USD",
            ),
        ]

        ablations = [
            AblationExperiment(
                name="Without Reasoning Engine",
                description="Remove the core reasoning module, use direct prediction",
                what_to_remove="Reasoning Engine module",
                expected_impact="Significant accuracy drop (>15%)",
            ),
            AblationExperiment(
                name="Without Validation Layer",
                description="Remove output validation, accept all raw outputs",
                what_to_remove="Validation Layer",
                expected_impact="Higher hallucination rate, lower trustworthiness",
            ),
            AblationExperiment(
                name="Single-Pass vs Multi-Pass",
                description="Compare single-pass execution against iterative refinement",
                what_to_remove="Iterative refinement loops",
                expected_impact="5-10% accuracy loss, 50% latency reduction",
            ),
        ]

        return EvaluationPlan(
            idea_id=idea_id,
            title=title,
            datasets=datasets,
            baselines=baselines,
            metrics=metrics,
            ablations=ablations,
        )

    def _parse_llm_plan(self, idea: dict, llm_output: str) -> EvaluationPlan:
        """Parse LLM output into EvaluationPlan. Falls back to template on parse error."""
        try:
            import json
            data = json.loads(llm_output)
            # Map LLM output to EvaluationPlan
            return EvaluationPlan(
                idea_id=idea.get("id", 0),
                title=idea.get("title", ""),
                datasets=[DatasetRecommendation(**d) for d in data.get("datasets", [])],
                baselines=[BaselineMethod(**b) for b in data.get("baselines", [])],
                metrics=[MetricTarget(**m) for m in data.get("metrics", [])],
                ablations=[AblationExperiment(**a) for a in data.get("ablations", [])],
            )
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning("Failed to parse LLM plan output: %s", e)
            return self._generate_template(idea)
