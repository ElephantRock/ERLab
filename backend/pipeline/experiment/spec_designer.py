"""EAD-1: Deterministic experiment spec designer.

Compiles a research idea + registered dataset metadata + a closed
supported capability into validated ``ExperimentSpec`` objects. Does NOT
generate executable code, does NOT execute experiments, and does NOT
write specs into ``data/datasets/``.

The designer is a compiler into the existing trusted execution system,
not a code generator. It maps idea/question fields onto the spec schema
using only declared supported capabilities.

Failure modes are explicit and structured:
- ``insufficient_compatible_datasets`` — fewer than ``min_datasets``
- ``unsupported_task`` — no capability for the derivable task type
- ``unsupported_metric`` — idea requests a metric not in the capability
- ``dataset_metadata_error`` — malformed metadata or hash mismatch
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from backend.pipeline.experiment.dataset_registry import (
    DatasetMetadata,
    list_registered_datasets,
    load_dataset_metadata,
)
from backend.pipeline.experiment.specification import (
    SpecValidationError,
    _parse_spec,
)

logger = logging.getLogger(__name__)


class DesignError(ValueError):
    """Raised when experiment design compilation fails."""


@dataclass(frozen=True)
class SupportedCapability:
    """A closed contract for one supported experiment family.

    Defines the legal method identity, metrics, baseline, and
    entrypoint. The designer may only produce specs whose fields
    come from this contract.
    """

    task_type: str                      # "classification" | "regression"
    supported_metrics: dict[str, str]   # metric_name -> direction
    baseline_method: str                # e.g. "majority_class"
    comparison_method: str              # e.g. "logistic_regression"
    analysis_entrypoint: str            # checked-in path
    analysis_method_description: str    # human-readable
    model_family: str = ""
    allowed_hyperparameters: dict[str, Any] = field(default_factory=dict)
    # Frozen implementation truth, transcribed from the checked-in
    # entrypoint. Each fact carries the canonical statement (injected
    # verbatim into paper synthesis and remediation prompts so the LLM
    # never infers implementation details) plus the pattern contract the
    # method_fidelity gate enforces: every required pattern must appear
    # in the paper, no forbidden pattern may appear anywhere.
    method_facts: dict[str, dict[str, Any]] = field(default_factory=dict)


# ── Production capability for Case 1 ────────────────────────────────────────
# The checked-in v1 entrypoint implements a fixed protocol:
# logistic regression with post-hoc calibration (sigmoid/isotonic)
# vs majority-class baseline, evaluated under fixed covariate-shift
# severities with selective-classification metrics (AURC, ECE, accuracy).
# Protocol constants (severities, calibration methods, seed) are frozen
# inside the entrypoint, not configurable through hyperparameters.

TABULAR_CALIBRATION_SELECTIVE_V1 = SupportedCapability(
    task_type="classification",
    supported_metrics={
        "baseline_accuracy": "higher_better",
        "0_0_uncalibrated_accuracy": "higher_better",
        "0_0_uncalibrated_ece": "lower_better",
        "0_0_uncalibrated_aurc": "lower_better",
        "0_0_sigmoid_accuracy": "higher_better",
        "0_0_sigmoid_ece": "lower_better",
        "0_0_sigmoid_aurc": "lower_better",
        "0_0_isotonic_accuracy": "higher_better",
        "0_0_isotonic_ece": "lower_better",
        "0_0_isotonic_aurc": "lower_better",
        "0_25_uncalibrated_accuracy": "higher_better",
        "0_25_uncalibrated_ece": "lower_better",
        "0_25_uncalibrated_aurc": "lower_better",
        "0_25_sigmoid_accuracy": "higher_better",
        "0_25_sigmoid_ece": "lower_better",
        "0_25_sigmoid_aurc": "lower_better",
        "0_25_isotonic_accuracy": "higher_better",
        "0_25_isotonic_ece": "lower_better",
        "0_25_isotonic_aurc": "lower_better",
        "0_5_uncalibrated_accuracy": "higher_better",
        "0_5_uncalibrated_ece": "lower_better",
        "0_5_uncalibrated_aurc": "lower_better",
        "0_5_sigmoid_accuracy": "higher_better",
        "0_5_sigmoid_ece": "lower_better",
        "0_5_sigmoid_aurc": "lower_better",
        "0_5_isotonic_accuracy": "higher_better",
        "0_5_isotonic_ece": "lower_better",
        "0_5_isotonic_aurc": "lower_better",
        "0_75_uncalibrated_accuracy": "higher_better",
        "0_75_uncalibrated_ece": "lower_better",
        "0_75_uncalibrated_aurc": "lower_better",
        "0_75_sigmoid_accuracy": "higher_better",
        "0_75_sigmoid_ece": "lower_better",
        "0_75_sigmoid_aurc": "lower_better",
        "0_75_isotonic_accuracy": "higher_better",
        "0_75_isotonic_ece": "lower_better",
        "0_75_isotonic_aurc": "lower_better",
    },
    baseline_method="majority_class",
    comparison_method="logistic_regression",
    analysis_entrypoint=(
        "experiments/tabular_calibration_selective_v1/analysis.py"
    ),
    analysis_method_description=(
        "logistic regression with post-hoc calibration"
        " (sigmoid/isotonic) vs majority-class baseline"
        " under fixed covariate-shift severities"
    ),
    model_family="logistic_regression",
    # Transcribed from experiments/tabular_calibration_selective_v1/
    # analysis.py (constants at module top; implementations at the named
    # functions). The released run-2713 paper misdescribed all four of
    # these facts and no gate caught it — these statements are now the
    # only source the paper may draw methodology claims from.
    method_facts={
        "base_model": {
            "statement": (
                "The base model is a set of independent one-vs-rest"
                " binary logistic regression classifiers. Each binary"
                " model is trained with full-batch gradient descent"
                " (learning rate 0.05, 1000 epochs, L2 penalty 0.001)"
                " implemented from first principles; no external"
                " machine-learning library is used. Per-class scores"
                " are combined into class probabilities by softmax"
                " normalization of the per-class logits."
            ),
            "required_patterns": [
                r"one[-. ]vs[. -]rest|one versus rest|one-vs-all",
                r"gradient[- ]descent|gradient descent",
            ],
            "forbidden_patterns": [
                r"multiclass cross-entropy",
                r"multinomial logistic",
                r"softmax logistic",
                r"softmax regression",
                r"library default",
                r"implementation librar",
                r"scikit-learn|sklearn",
            ],
        },
        "calibration_scheme": {
            "statement": (
                "Post-hoc calibration is fitted only for the designated"
                " positive class (the last class in sorted label order)."
                " Sigmoid (Platt-style) parameters are selected by grid"
                " search over a fixed candidate set of (a, b) values"
                " minimizing binary cross-entropy on the calibration"
                " split; an isotonic map (pool-adjacent-violators) is"
                " fitted on the positive-class probability against the"
                " indicator y = positive class. At application time only"
                " the positive-class probability is calibrated; the"
                " remaining probability mass is redistributed across"
                " the other classes proportionally to their"
                " uncalibrated probabilities."
            ),
            "required_patterns": [
                r"positive[- ]class",
                r"redistribut",
            ],
            "forbidden_patterns": [
                r"per-class (?:calibrat|mapping|map\b)",
                r"fits,? per class",
                r"calibrat\w* (?:is |are )?(?:fitted|trained|learned|"
                r"applied) (?:independently |separately )?"
                r"(?:for|to|on) each class",
            ],
        },
        "ece_definition": {
            "statement": (
                "Expected calibration error (ECE) is computed with 10"
                " equal-width bins on the positive-class probability:"
                " within each bin it compares the mean positive-class"
                " probability against the empirical frequency of the"
                " positive class (y = positive class), and averages the"
                " absolute gaps weighted by bin size. It is not the"
                " standard top-class-confidence ECE."
            ),
            "required_patterns": [
                r"(?:ece|expected calibration error)[^.]{0,200}"
                r"positive[- ]class"
                r"|positive[- ]class[^.]{0,200}"
                r"(?:ece|expected calibration error)",
            ],
            "forbidden_patterns": [
                r"(?:ece|expected calibration error)[^.]{0,200}"
                r"confidence of the predicted class",
                r"(?:ece|expected calibration error)[^.]{0,200}"
                r"predicted[- ]class correctness",
                r"(?:ece|expected calibration error)[^.]{0,200}"
                r"bins by confidence",
                r"(?:ece|expected calibration error)[^.]{0,200}"
                r"binned accuracy and mean confidence",
            ],
        },
        "aurc_definition": {
            "statement": (
                "The area under the risk-coverage curve (AURC) is"
                " estimated by evaluating selective risk and coverage at"
                " ten fixed confidence thresholds (0.0 to 0.9 in steps"
                " of 0.1), using the maximum class probability as the"
                " confidence score and correctness of the predicted"
                " class as the risk basis, then trapezoid-integrating"
                " those ten (coverage, risk) points. It is not an"
                " integral over the full sample ordering."
            ),
            "required_patterns": [
                r"(?:ten|10) fixed (?:confidence )?thresholds",
            ],
            "forbidden_patterns": [
                r"rank[- ]based",
                r"sorting instances by decreasing confidence",
                r"swept from full coverage",
            ],
        },
    },
)


@dataclass
class DesignResult:
    """Outcome of design compilation."""

    status: str                         # "success" | failure reason
    specs: list = field(default_factory=list)  # list[ExperimentSpec]
    diagnostics: list[str] = field(default_factory=list)


@dataclass
class IdeaInputs:
    """Minimal structured inputs from a ResearchIdea.

    Extracted from ``ResearchIdea`` free-text fields by the caller.
    The designer does not parse prose.
    """

    proposed_method: str = ""
    evaluation_approach: str = ""
    requested_metrics: list[str] = field(default_factory=list)


def _select_metrics(
    requested: list[str],
    capability: SupportedCapability,
) -> list[str]:
    """Intersect requested metrics with capability's supported set.

    Returns the subset of requested metrics that the capability supports.
    Raises ``DesignError`` if the primary requested metric is unsupported.
    """
    supported = set(capability.supported_metrics.keys())
    matched = [m for m in requested if m in supported]
    unmatched = [m for m in requested if m not in supported]

    if unmatched:
        logger.info(
            "Design: ignoring unsupported metrics: %s", unmatched,
        )

    if not matched:
        raise DesignError(
            f"None of the requested metrics {requested} are supported"
            f" by capability ({sorted(supported)})"
        )

    return matched


def _build_spec_dict(
    dataset: DatasetMetadata,
    capability: SupportedCapability,
    research_question: str,
    declared_metrics: list[str],
    spec_id: str,
    hyperparameters: dict[str, Any] | None = None,
) -> dict:
    """Serialize a single ExperimentSpec as a raw dict."""
    metric_directions = {
        m: {"direction": capability.supported_metrics[m]}
        for m in declared_metrics
        if m in capability.supported_metrics
    }
    return {
        "experiment_spec_id": spec_id,
        "description": (
            f"Autonomous design: {capability.comparison_method}"
            f" vs {capability.baseline_method} on {dataset.name}"
        ),
        "dataset": {
            "name": dataset.name,
            "version": dataset.version,
            "raw_filename": dataset.raw_filename,
            "raw_sha256": dataset.raw_sha256,
        },
        "split": {
            "method": (
                "stratified by target, first 80% train /"
                " last 20% test, fixed shuffle"
                if dataset.is_classification
                else "first 80% train / last 20% test, fixed shuffle"
            ),
            "train_fraction": 0.8,
            "test_fraction": 0.2,
            "random_seed": 42,
        },
        "analysis": {
            "entrypoint": capability.analysis_entrypoint,
            "method": capability.analysis_method_description,
            "declared_metrics": declared_metrics,
        },
        "metrics": metric_directions,
        "tolerances": {m: 0.001 for m in declared_metrics},
        "output_artifacts": ["metrics.json"],
        "research_question": research_question,
        "research_intent": {
            "task_type": capability.task_type,
            "target_name": dataset.target,
            "baseline_method": capability.baseline_method,
            "comparison_method": capability.comparison_method,
            "primary_metric": declared_metrics[0],
        },
        "model_family": capability.model_family,
        "hyperparameters": hyperparameters or capability.allowed_hyperparameters,
    }


class SpecDesigner:
    """Deterministic compiler from idea → validated experiment specs.

    Does not generate code. Does not execute. Does not write files.
    Produces in-memory ``ExperimentSpec`` objects that pass
    ``_parse_spec()`` validation.
    """

    def design(
        self,
        *,
        research_question: str,
        idea: IdeaInputs,
        capability: SupportedCapability,
        min_datasets: int = 2,
        datasets_dir: Any = None,
    ) -> DesignResult:
        """Compile experiment specs from idea + capability + registry.

        Returns ``DesignResult``. On success, ``specs`` contains one
        validated ``ExperimentSpec`` per compatible dataset. On failure,
        ``status`` explains why and ``diagnostics`` has details.
        """
        diagnostics: list[str] = []

        # 1. Select metrics from the idea's requests.
        try:
            declared_metrics = _select_metrics(
                idea.requested_metrics, capability,
            )
        except DesignError as e:
            return DesignResult(
                status="unsupported_metric",
                diagnostics=[str(e)],
            )

        # 2. Enumerate registered datasets and filter by task type.
        all_names = list_registered_datasets(datasets_dir)
        compatible: list[DatasetMetadata] = []

        for name in all_names:
            try:
                meta = load_dataset_metadata(name, datasets_dir)
            except (FileNotFoundError, ValueError) as e:
                diagnostics.append(f"dataset '{name}': {e}")
                continue

            if meta.task_type != capability.task_type:
                diagnostics.append(
                    f"dataset '{name}': task_type {meta.task_type}"
                    f" != capability {capability.task_type}"
                )
                continue

            compatible.append(meta)

        if len(compatible) < min_datasets:
            return DesignResult(
                status="insufficient_compatible_datasets",
                diagnostics=(
                    diagnostics
                    + [
                        f"Found {len(compatible)} compatible dataset(s),"
                        f" need at least {min_datasets}",
                    ]
                ),
            )

        # 3. Compile one spec per compatible dataset.
        specs = []
        for ds in compatible:
            spec_id = f"auto-{capability.task_type}-{ds.name}"
            raw = _build_spec_dict(
                dataset=ds,
                capability=capability,
                research_question=research_question,
                declared_metrics=declared_metrics,
                spec_id=spec_id,
            )

            # 4. Validate through the hardened _parse_spec.
            try:
                spec = _parse_spec(raw)
            except SpecValidationError as e:
                return DesignResult(
                    status="spec_validation_failed",
                    diagnostics=[
                        f"dataset '{ds.name}': {e}",
                    ],
                )

            specs.append(spec)
            diagnostics.append(
                f"dataset '{ds.name}': spec compiled and validated",
            )

        return DesignResult(
            status="success",
            specs=specs,
            diagnostics=diagnostics,
        )
