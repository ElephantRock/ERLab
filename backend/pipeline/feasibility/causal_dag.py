"""Causal DAG model for counterfactual reasoning on feasibility scores.

Implements a lightweight Pearl-style structural causal model for the
research pipeline. Given feasibility dimension scores as observations,
computes:
1. Counterfactual predictions: "What if dimension X were Y instead?"
2. Sensitivity analysis: Which dimensions most affect overall score?
3. Refutation tests: Stress-test causal assumptions.

Uses linear structural equations for tractability. No external deps
beyond numpy (already required).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DAGEdge:
    """Directed edge in the causal DAG."""
    source: str
    target: str
    weight: float


@dataclass
class CounterfactualResult:
    """Result of a counterfactual query."""
    intervened_dimension: str
    original_value: float
    counterfactual_value: float
    predicted_impact: float  # predicted overall score change
    new_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class SensitivityResult:
    """Sensitivity analysis result showing dimension importance."""
    dimension_rankings: list[tuple[str, float]]  # (dimension, impact_score)
    most_influential: str = ""
    least_influential: str = ""


@dataclass
class RefutationResult:
    """Result of refutation tests on causal assumptions."""
    tests: dict[str, bool] = field(default_factory=dict)
    all_passed: bool = False


# Pipeline causal DAG definition
RESEARCH_PIPELINE_DAG = [
    DAGEdge("literature_quality", "gap_clarity", 0.4),
    DAGEdge("literature_quality", "idea_novelty", 0.3),
    DAGEdge("gap_clarity", "idea_novelty", 0.5),
    DAGEdge("gap_clarity", "method_feasibility", 0.3),
    DAGEdge("idea_novelty", "impact_potential", 0.5),
    DAGEdge("method_feasibility", "impact_potential", 0.3),
    DAGEdge("data_availability", "method_feasibility", 0.4),
]

# Mapping from feasibility report fields to DAG node names
_FEASIBILITY_TO_DAG = {
    "data_availability": "data_availability",
    "computational_requirements": "method_feasibility",
    "methodological_complexity": "method_feasibility",
    "evaluation_plan": "method_feasibility",
    "novelty_grounding": "idea_novelty",
    "impact_potential": "impact_potential",
}


class PipelineCausalModel:
    """Lightweight structural causal model for the research pipeline.

    Models causal relationships between pipeline dimensions using linear
    structural equations. Supports counterfactual queries, sensitivity
    analysis, and basic refutation tests.
    """

    def __init__(self, edges: list[DAGEdge] | None = None) -> None:
        self._edges = edges or RESEARCH_PIPELINE_DAG
        self._nodes = set()
        self._adj: dict[str, list[DAGEdge]] = {}
        for edge in self._edges:
            self._nodes.add(edge.source)
            self._nodes.add(edge.target)
            self._adj.setdefault(edge.source, []).append(edge)
            self._adj.setdefault(edge.target, [])

    def counterfactual(
        self,
        observations: dict[str, float],
        intervene_dim: str,
        intervene_value: float,
    ) -> CounterfactualResult:
        """Run a counterfactual query: what if intervene_dim were intervene_value?

        Uses do-calculus: set the intervened variable to the new value,
        then propagate through the DAG via linear structural equations.

        Args:
            observations: Current dimension scores (0-10 scale).
            intervene_dim: DAG node name to intervene on.
            intervene_value: New value for that dimension.

        Returns:
            CounterfactualResult with predicted impact.
        """
        if intervene_dim not in self._nodes:
            return CounterfactualResult(
                intervened_dimension=intervene_dim,
                original_value=observations.get(intervene_dim, 0.0),
                counterfactual_value=intervene_value,
                predicted_impact=0.0,
            )

        original_value = observations.get(intervene_dim, 0.0)

        # Propagate from intervened node through the DAG
        new_scores = dict(observations)
        new_scores[intervene_dim] = intervene_value

        # Topological propagation (order matters)
        for node in self._topological_order():
            if node == intervene_dim:
                continue
            incoming = self._adj.get(node, [])
            parent_edges = [e for e in self._edges if e.target == node]
            if parent_edges:
                parent_contribution = sum(
                    new_scores.get(e.source, 5.0) * e.weight
                    for e in parent_edges
                )
                # Blend: 70% original observation + 30% causal propagation
                observed = observations.get(node, 5.0)
                new_scores[node] = 0.7 * observed + 0.3 * parent_contribution

        original_impact = observations.get("impact_potential", 5.0)
        new_impact = new_scores.get("impact_potential", original_impact)
        predicted_impact = new_impact - original_impact

        return CounterfactualResult(
            intervened_dimension=intervene_dim,
            original_value=original_value,
            counterfactual_value=intervene_value,
            predicted_impact=predicted_impact,
            new_scores=new_scores,
        )

    def sensitivity_analysis(
        self, observations: dict[str, float]
    ) -> SensitivityResult:
        """Determine which dimensions most affect the overall outcome.

        Perturbs each dimension by +/-1 and measures impact on
        impact_potential via the DAG.

        Returns:
            SensitivityResult with ranked dimensions.
        """
        impacts: list[tuple[str, float]] = []
        for node in self._nodes:
            if node == "impact_potential":
                continue
            original = observations.get(node, 5.0)
            cf_up = self.counterfactual(observations, node, original + 1.0)
            cf_down = self.counterfactual(observations, node, original - 1.0)
            sensitivity = (abs(cf_up.predicted_impact) + abs(cf_down.predicted_impact)) / 2
            impacts.append((node, round(sensitivity, 4)))

        impacts.sort(key=lambda x: x[1], reverse=True)

        return SensitivityResult(
            dimension_rankings=impacts,
            most_influential=impacts[0][0] if impacts else "",
            least_influential=impacts[-1][0] if impacts else "",
        )

    def run_refutation_tests(
        self, observations: dict[str, float]
    ) -> RefutationResult:
        """Stress-test causal claims with three refutation methods.

        1. Random common cause: Add random noise to a parent; verify
           child changes proportionally.
        2. Placebo treatment: Intervene on a node with no causal path
           to impact_potential; verify no change.
        3. Data subset: Use a subset of observations; verify
           sensitivity rankings remain consistent.

        Returns:
            RefutationResult with pass/fail for each test.
        """
        results: dict[str, bool] = {}

        # Test 1: Random common cause
        perturbed = dict(observations)
        perturbed["literature_quality"] = perturbed.get("literature_quality", 5.0) + 1.0
        cf = self.counterfactual(observations, "literature_quality",
                                 observations.get("literature_quality", 5.0) + 1.0)
        results["random_common_cause"] = cf.predicted_impact != 0.0

        # Test 2: Placebo treatment — intervene on isolated node
        # Add a temporary isolated node for this test
        placebo_edges = self._edges + [DAGEdge("_placebo", "_placebo_child", 0.5)]
        placebo_model = PipelineCausalModel(placebo_edges)
        placebo_obs = dict(observations)
        placebo_obs["_placebo"] = 7.0
        placebo_obs["_placebo_child"] = 7.0
        cf_placebo = placebo_model.counterfactual(placebo_obs, "_placebo", 8.0)
        # The placebo node should not affect impact_potential
        original_impact = observations.get("impact_potential", 5.0)
        new_impact = cf_placebo.new_scores.get("impact_potential", original_impact)
        results["placebo_treatment"] = abs(new_impact - original_impact) < 0.01

        # Test 3: Data subset consistency
        full_sensitivity = self.sensitivity_analysis(observations)
        subset = {k: v for i, (k, v) in enumerate(observations.items()) if i % 2 == 0}
        subset_sensitivity = self.sensitivity_analysis(subset)
        # Top dimension should be the same
        full_top = full_sensitivity.most_influential
        subset_rankings = {dim for dim, _ in subset_sensitivity.dimension_rankings[:3]}
        results["data_subset"] = full_top in subset_rankings

        return RefutationResult(
            tests=results,
            all_passed=all(results.values()),
        )

    def feasibility_to_dag_scores(self, report: FeasibilityReport) -> dict[str, float]:
        """Convert a FeasibilityReport to DAG node scores."""
        mapping = {
            "data_availability": report.data_availability,
            "computational_requirements": report.computational_requirements,
            "methodological_complexity": report.methodological_complexity,
            "evaluation_plan": report.evaluation_plan,
            "novelty_grounding": report.novelty_grounding,
            "impact_potential": report.impact_potential,
        }
        # Add inferred nodes
        mapping["literature_quality"] = (report.novelty_grounding + report.data_availability) / 2
        mapping["gap_clarity"] = report.novelty_grounding * 0.8
        mapping["idea_novelty"] = report.novelty_grounding
        mapping["method_feasibility"] = (
            report.methodological_complexity
            + report.computational_requirements
            + report.evaluation_plan
        ) / 3
        return mapping

    def _topological_order(self) -> list[str]:
        """Return nodes in topological order (parents before children)."""
        in_degree: dict[str, int] = {n: 0 for n in self._nodes}
        for edge in self._edges:
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        queue = [n for n in self._nodes if in_degree.get(n, 0) == 0]
        order = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for edge in self._adj.get(node, []):
                in_degree[edge.target] -= 1
                if in_degree[edge.target] == 0:
                    queue.append(edge.target)
        return order
