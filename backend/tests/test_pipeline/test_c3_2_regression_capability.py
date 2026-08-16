"""C3-2: Capability #2 — declaration, entrypoint, and harvest proofs.

TABULAR_ROBUST_REGRESSION_V1 plugs in through extension surfaces only:
the capability declaration, one checked-in entrypoint, and the
governed dataset files. These tests prove the frozen protocol executes
deterministically, the capability is registered and routes correctly,
its method facts are self-consistent, and the generic Unicode-digit
fold lets the frozen input's "R²" harvest the R2 metrics.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

from backend.pipeline.evaluation.method_fidelity import (
    evaluate_method_fidelity,
)
from backend.pipeline.experiment.spec_designer import (
    TABULAR_CALIBRATION_SELECTIVE_V1,
    TABULAR_ROBUST_REGRESSION_V1,
    list_supported_capabilities,
    select_capability,
)
from backend.pipeline.stages import (
    StageContext,
    ensure_autonomous_experiment_design,
)

CASE3_DOMAIN = "Robust regression under distribution shift"
CASE3_QUESTION = (
    "Are robust-regression method rankings stable as covariate"
    " perturbation severity increases, or do rank reversals occur"
    " in MAE, RMSE, and R² across tabular regression datasets?"
)

ENTRYPOINT = "experiments/tabular_robust_regression_v1/analysis.py"


def _run_entrypoint(input_path: str, out_dir: str):
    return subprocess.run(
        [sys.executable, ENTRYPOINT, "--input", input_path,
         "--output", out_dir],
        capture_output=True, text=True, cwd=".",
    )


class TestEntrypointExecution:
    def test_airfoil_executes_with_valid_metrics(self):
        with tempfile.TemporaryDirectory() as out:
            r = _run_entrypoint(
                "data/datasets/airfoil_self_noise/airfoil_self_noise.dat",
                out,
            )
            assert r.returncode == 0, r.stderr
            with open(f"{out}/metrics.json") as f:
                m = json.load(f)
            assert m["experiment_spec_id"] == "tabular-robust-regression-v1"
            assert len(m["metrics"]) == 27
            assert all(isinstance(v, float) for v in m["metrics"].values())

    def test_concrete_executes_with_valid_metrics(self):
        with tempfile.TemporaryDirectory() as out:
            r = _run_entrypoint(
                "data/datasets/concrete_strength/concrete_raw.csv", out,
            )
            assert r.returncode == 0, r.stderr
            with open(f"{out}/metrics.json") as f:
                m = json.load(f)
            assert len(m["metrics"]) == 27

    def test_execution_is_deterministic(self):
        with tempfile.TemporaryDirectory() as d1, \
                tempfile.TemporaryDirectory() as d2:
            _run_entrypoint(
                "data/datasets/airfoil_self_noise/airfoil_self_noise.dat",
                d1,
            )
            _run_entrypoint(
                "data/datasets/airfoil_self_noise/airfoil_self_noise.dat",
                d2,
            )
            with open(f"{d1}/metrics.json", "rb") as f:
                a = f.read()
            with open(f"{d2}/metrics.json", "rb") as f:
                b = f.read()
            assert a == b

    def test_flat_metric_layout_matches_frozen_protocol(self):
        with tempfile.TemporaryDirectory() as out:
            _run_entrypoint(
                "data/datasets/airfoil_self_noise/airfoil_self_noise.dat",
                out,
            )
            with open(f"{out}/metrics.json") as f:
                m = json.load(f)["metrics"]
            for sev in ("0_0", "0_25", "0_5", "0_75"):
                for meth in ("ridge", "huber"):
                    for met in ("mae", "rmse", "r2"):
                        assert f"{sev}_{meth}_{met}" in m
            for met in ("mae", "rmse", "r2"):
                assert f"baseline_{met}" in m

    def test_baseline_is_severity_independent_by_construction(self):
        with tempfile.TemporaryDirectory() as out:
            _run_entrypoint(
                "data/datasets/airfoil_self_noise/airfoil_self_noise.dat",
                out,
            )
            with open(f"{out}/condition_metrics.json") as f:
                conds = json.load(f)
            assert len(conds) == 8  # 4 severities x 2 methods; no baseline rows


class TestCapabilityDeclaration:
    def test_registry_contains_both_capabilities(self):
        ids = [c.capability_id for c in list_supported_capabilities()]
        assert ids == [
            "tabular_calibration_selective_v1",
            "tabular_robust_regression_v1",
        ]

    def test_frozen_input_routing(self):
        assert select_capability(
            f"{CASE3_QUESTION} {CASE3_DOMAIN}"
        ).capability_id == "tabular_robust_regression_v1"
        case1_q = (
            "How does post-hoc probability calibration affect"
            " selective classification performance under covariate"
            " shift in tabular classification, and are the effects"
            " consistent across datasets and shift severities?"
        )
        assert select_capability(
            f"{case1_q} Robust and reliable machine learning under"
            " distribution shift"
        ).capability_id == "tabular_calibration_selective_v1"
        assert select_capability(
            "compare logistic regression classifiers calibration accuracy"
        ).capability_id == "tabular_calibration_selective_v1"

    def test_method_facts_are_self_consistent(self):
        paper = "# T\n\n## Methodology\n\n" + "\n\n".join(
            f["statement"] for f in
            TABULAR_ROBUST_REGRESSION_V1.method_facts.values()
        )
        res = evaluate_method_fidelity(
            paper, TABULAR_ROBUST_REGRESSION_V1.method_facts,
        )
        assert res.passed, res.violations

    def test_calibration_facts_still_self_consistent(self):
        paper = "# T\n\n" + "\n\n".join(
            f["statement"] for f in
            TABULAR_CALIBRATION_SELECTIVE_V1.method_facts.values()
        )
        assert evaluate_method_fidelity(
            paper, TABULAR_CALIBRATION_SELECTIVE_V1.method_facts,
        ).passed


class TestHarvestFold:
    def test_case3_input_harvests_all_metrics_including_r2(self):
        """The frozen question writes R² with a Unicode superscript;
        the generic fold must let the ASCII _r2 metrics harvest, or
        the paper would lack the R² results its own question asks
        about."""
        ctx = _ctx_for_case3()
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]

        assert design["status"] == "designed"
        assert design["capability_id"] == "tabular_robust_regression_v1"
        spec_ids = [s["experiment_spec_id"] for s in design["specs"]]
        assert spec_ids == [
            "auto-regression-airfoil_self_noise",
            "auto-regression-concrete_strength",
        ]
        declared = design["specs"][0]["analysis"]["declared_metrics"]
        assert len(declared) == 27
        assert sum(1 for m in declared if m.endswith("_r2")) == 9
        assert "baseline_mae" in declared
        assert design["paper_directive"].startswith(
            "The paper must describe the actual robust-regression"
        )

    def test_case1_harvest_set_unchanged(self):
        """Genericity proof: the fold does not alter the Case-1
        harvest — every calibration metric still requests."""
        ctx = _ctx_for_case1()
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]
        assert design["status"] == "designed"
        declared = set(design["specs"][0]["analysis"]["declared_metrics"])
        assert declared == set(
            TABULAR_CALIBRATION_SELECTIVE_V1.supported_metrics.keys()
        )


# ── fixtures ────────────────────────────────────────────────────────────────


def _ctx_for_case3() -> StageContext:
    from backend.pipeline.generation.models import ResearchIdea
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.synthesis.proposal_synthesizer import (
        FeasibilityReport,
    )

    ctx = StageContext(
        result=PipelineResult(),
        domain=CASE3_DOMAIN,
        research_question=CASE3_QUESTION,
    )
    ctx.params["autonomous_experiment_enabled"] = True
    ctx.result.ideas = [ResearchIdea(
        title="Robust regression ranking stability",
        problem_statement="rank stability of robust regression under shift",
        proposed_method="huber regression vs ridge",
        expected_contributions="empirical ranking map",
        novelty_rationale="first controlled perturbation ranking study",
        evaluation_approach="mae rmse r2 regression robustness metrics",
        domain="ML", round_generated=1, score=0.8,
        supporting_papers=[], source_gap_ids=[],
    )]
    ctx.result.feasibility_reports = {0: FeasibilityReport(
        overall_score=0.8, data_availability=7,
        computational_requirements=8, methodological_complexity=7,
        evaluation_plan=8, novelty_grounding=6, impact_potential=7,
        reasoning="ok", estimated_timeline="2w", key_risks=[],
    )}
    ctx.result.proposals = {0: SimpleNamespace(
        title="T", to_markdown=lambda: "t",
    )}
    return ctx


def _ctx_for_case1() -> StageContext:
    from backend.pipeline.generation.models import ResearchIdea
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.synthesis.proposal_synthesizer import (
        FeasibilityReport,
    )

    ctx = StageContext(
        result=PipelineResult(),
        domain="Robust and reliable machine learning under distribution shift",
        research_question=(
            "How does post-hoc probability calibration affect selective"
            " classification performance under covariate shift in"
            " tabular classification, and are the effects consistent"
            " across datasets and shift severities?"
        ),
    )
    ctx.params["autonomous_experiment_enabled"] = True
    ctx.result.ideas = [ResearchIdea(
        title="Calibration Study",
        problem_statement="calibration selective classification",
        proposed_method="temperature scaling logistic regression",
        expected_contributions="better selective classification",
        novelty_rationale="novel combination",
        evaluation_approach="accuracy calibration metrics ece aurc",
        domain="ML", round_generated=1, score=0.8,
        supporting_papers=[], source_gap_ids=[],
    )]
    ctx.result.feasibility_reports = {0: FeasibilityReport(
        overall_score=0.8, data_availability=7,
        computational_requirements=8,
        methodological_complexity=7, evaluation_plan=8,
        novelty_grounding=6, impact_potential=7,
        reasoning="ok", estimated_timeline="2w", key_risks=[],
    )}
    ctx.result.proposals = {0: SimpleNamespace(
        title="T", to_markdown=lambda: "t",
    )}
    return ctx
