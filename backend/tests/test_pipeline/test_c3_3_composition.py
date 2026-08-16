"""C3-3: composition proofs — Capability #2 through the real common
path, with negative controls.

The central invariants:
  - Live results == persisted results == cold-hydrated results.
  - Capability #2 reaches design/execution/persistence/hydration/
    context/assurance without a Capability-#2 branch in any of them.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.database as db_mod
import backend.pipeline.stages as stages_mod
from backend.db.database import Base
from backend.db.models import ExperimentResult, Idea, PipelineRun, Proposal
from backend.pipeline.evaluation.method_fidelity import (
    evaluate_method_fidelity,
)
from backend.pipeline.experiment.spec_designer import (
    TABULAR_ROBUST_REGRESSION_V1,
)
from backend.pipeline.stages import (
    ExperimentExecutionStage,
    PaperSynthesisStage,
    StageContext,
    ensure_autonomous_experiment_design,
)

CASE3_DOMAIN = "Robust regression under distribution shift"
CASE3_QUESTION = (
    "Are robust-regression method rankings stable as covariate"
    " perturbation severity increases, or do rank reversals occur"
    " in MAE, RMSE, and R² across tabular regression datasets?"
)


def _make_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _fk(conn, record):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return engine


@contextmanager
def _patched_session(engine):
    test_sf = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def patched():
        session = test_sf()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    orig = db_mod.get_session
    db_mod.get_session = patched
    stages_mod.get_session = patched
    db_mod._get_engine = lambda: engine
    try:
        yield
    finally:
        db_mod.get_session = orig
        stages_mod.get_session = orig


def _seed(engine) -> tuple[int, int, int]:
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    run = PipelineRun(
        run_id_str="run_c3_3", domain="ML", status="running",
        config_json="{}", stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()
    idea = Idea(
        title="Robust regression ranking stability",
        problem_statement="p", proposed_method="huber vs ridge",
        expected_contributions="c", domain="ML",
        novelty_score=0.5, feasibility_score=0.8, overall_score=0.8,
        pipeline_run_id=run.id,
    )
    session.add(idea)
    session.commit()
    proposal = Proposal(idea_id=idea.id, content_md="t")
    session.add(proposal)
    session.commit()
    ids = (run.id, idea.id, proposal.id)
    session.close()
    return ids


def _ctx(run_id: int) -> StageContext:
    from backend.pipeline.generation.models import ResearchIdea
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.synthesis.proposal_synthesizer import (
        FeasibilityReport,
    )

    ctx = StageContext(
        result=PipelineResult(),
        domain=CASE3_DOMAIN,
        research_question=CASE3_QUESTION,
        db_run_id=run_id,
    )
    ctx.params["autonomous_experiment_enabled"] = True
    ctx.result.ideas = [ResearchIdea(
        title="Robust regression ranking stability",
        problem_statement="rank stability under perturbation",
        proposed_method="huber regression vs ridge",
        expected_contributions="empirical ranking map",
        novelty_rationale="first controlled ranking study",
        evaluation_approach="mae rmse r2 regression robustness",
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


class TestFullComposition:
    def test_design_execute_persist_hydrate_context(self):
        """Design → execute → persist → hydrate → context, all through
        the real common path, for Capability #2."""
        engine = _make_engine()
        run_id, idea_id, proposal_id = _seed(engine)

        with _patched_session(engine):
            ctx = _ctx(run_id)
            ensure_autonomous_experiment_design(ctx)
            design = ctx.params["autonomous_experiment_design"]
            assert design["status"] == "designed"
            assert design["capability_id"] == "tabular_robust_regression_v1"

            stage = ExperimentExecutionStage()
            ok = asyncio.run(stage._execute_autonomous(ctx, design))
            assert ok is True

            # Persisted: two ExperimentResults, both successful,
            # through the common executor (manifest spec id).
            Session = sessionmaker(bind=engine)
            session = Session()
            rows = session.execute(
                select(ExperimentResult).where(
                    ExperimentResult.proposal_id == proposal_id,
                )
            ).scalars().all()
            session.close()
            assert len(rows) == 2
            spec_ids = set()
            for row in rows:
                assert row.success is True
                mf = json.loads(row.manifest_json)
                spec_ids.add(mf["experiment_spec_id"])
            assert spec_ids == {
                "auto-regression-airfoil_self_noise",
                "auto-regression-concrete_strength",
            }

            # Live markers: dataset-qualified, 27 per dataset.
            selected = design["selected_proposal_idx"]
            live = list(ctx.result.result_markers[selected])
            assert len(live) == 54
            prefixes = {m.metric_name.split(".")[0] for m in live}
            assert prefixes == {
                "airfoil_self_noise", "concrete_strength",
            }
            exp_ids = {m.experiment_result_id for m in live}
            assert len(exp_ids) == 2

            # Cold hydration == live.
            paper_stage = PaperSynthesisStage()
            ctx.result.result_markers[selected] = []
            hydrated = paper_stage._hydrate_autonomous_result_markers(
                proposal_id, design,
            )
            assert len(hydrated) == len(live)
            for a, b in zip(live, hydrated, strict=True):
                assert a.marker == b.marker
                assert a.metric_name == b.metric_name
                assert a.observed_value == b.observed_value
                assert a.experiment_result_id == b.experiment_result_id

            # Paper context: frozen protocol block + regression facts
            # + the capability's paper directive. No regression branch
            # exists in the builder — it renders from the design.
            ctx.result.experiment_runs[selected] = [
                SimpleNamespace(
                    status="succeeded",
                    dataset=SimpleNamespace(name=nm),
                )
                for nm in ("airfoil_self_noise", "concrete_strength")
            ]
            ctx.result.result_markers[selected] = live
            context = paper_stage._build_autonomous_paper_context(
                ctx, design,
            )[selected]
            assert "EXECUTED PROTOCOL" in context
            for fact in (
                TABULAR_ROBUST_REGRESSION_V1.method_facts.values()
            ):
                assert fact["statement"] in context
            assert "robust-regression" in context

    def test_method_fidelity_enforces_regression_facts(self):
        facts = TABULAR_ROBUST_REGRESSION_V1.method_facts
        good = "# T\n\n## Methodology\n\n" + "\n\n".join(
            f["statement"] for f in facts.values()
        )
        assert evaluate_method_fidelity(good, facts).passed

        # A library/gradient-descent misdescription must block.
        bad = good.replace(
            "solved in closed form (lambda = 1.0,"
            " with the intercept left unregularized) by pure-Python"
            " Gaussian elimination.",
            "trained with mini-batch stochastic gradient descent using"
            " scikit-learn defaults.",
        )
        res = evaluate_method_fidelity(bad, facts)
        assert not res.passed
        assert any("contradicts" in v for v in res.violations)


class TestNegativeControls:
    def test_missing_regression_dataset_fails_design(self):
        """A registry with only ONE regression dataset cannot satisfy
        min_datasets=2 -> insufficient_compatible_datasets."""
        from pathlib import Path

        from backend.pipeline.experiment.dataset_registry import (
            load_dataset_metadata,
        )
        from backend.pipeline.experiment.spec_designer import (
            IdeaInputs,
            SpecDesigner,
        )
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(
                "data/datasets/concrete_strength",
                f"{tmp}/concrete_strength",
            )
            only_concrete = [
                load_dataset_metadata(
                    "concrete_strength", datasets_dir=Path(tmp),
                )
            ]
            designer = SpecDesigner()
            result = designer.design(
                research_question=CASE3_QUESTION,
                idea=IdeaInputs(
                    proposed_method="huber",
                    evaluation_approach="mae rmse r2",
                    requested_metrics=list(
                        TABULAR_ROBUST_REGRESSION_V1.supported_metrics
                    ),
                ),
                capability=TABULAR_ROBUST_REGRESSION_V1,
                min_datasets=2,
                datasets_dir=Path(tmp),
            )
            assert result.status == "insufficient_compatible_datasets"
            assert only_concrete

    def test_wrong_dataset_hash_fails_closed(self):
        from pathlib import Path

        from backend.pipeline.experiment.dataset_registry import (
            load_dataset_metadata,
        )
        with tempfile.TemporaryDirectory() as tmp:
            src = "data/datasets/airfoil_self_noise"
            shutil.copytree(src, f"{tmp}/airfoil_self_noise")
            # Tamper with the raw file so the recorded hash no longer
            # matches.
            raw = f"{tmp}/airfoil_self_noise/airfoil_self_noise.dat"
            with open(raw, "a") as data:
                data.write("9999\t0\t0.3\t71.3\t0.0026\t126.0\n")
            with pytest.raises(ValueError, match="hash mismatch"):
                load_dataset_metadata(
                    "airfoil_self_noise",
                    datasets_dir=Path(tmp),
                )

    def test_unregistered_entrypoint_fails_execution(self):
        from backend.pipeline.experiment.empirical_runner import (
            execute_experiment_spec,
        )
        from backend.pipeline.experiment.specification import (
            _parse_spec,
        )
        raw = {
            "experiment_spec_id": "c3-neg-1",
            "description": "negative control",
            "dataset": {
                "name": "airfoil_self_noise", "version": "1.0.0",
                "raw_filename": "airfoil_self_noise.dat",
                "raw_sha256": TABULAR_ROBUST_REGRESSION_V1
                .method_facts and "74c75fd71783f1e6b71f"
                "8a622b993dc592897a97cd689c5090a07147a1b097b3",
            },
            "split": {
                "method": "seeded shuffle 80/20", "train_fraction": 0.8,
                "test_fraction": 0.2, "random_seed": 42,
            },
            "analysis": {
                "entrypoint": "experiments/does_not_exist/analysis.py",
                "method": "x",
                "declared_metrics": ["baseline_mae"],
            },
            "metrics": {"baseline_mae": {"direction": "lower_better"}},
            "tolerances": {"baseline_mae": 0.001},
            "output_artifacts": ["metrics.json"],
            "research_question": CASE3_QUESTION,
            "research_intent": {
                "task_type": "regression", "target_name": "y",
                "baseline_method": "mean_predictor",
                "comparison_method": "ridge",
                "primary_metric": "baseline_mae",
            },
            "model_family": "linear_regression",
            "hyperparameters": {},
        }
        spec = _parse_spec(raw)
        import tempfile as _tf
        from pathlib import Path as _Path
        with _tf.TemporaryDirectory() as out:
            manifest, _out, _err, exit_code, _t = asyncio.run(
                execute_experiment_spec(
                    spec, _Path(out), timeout_seconds=30.0,
                )
            )
        # Fail-closed: the executor either raises on the unresolvable
        # entrypoint or returns a manifest whose status is not
        # succeeded with a nonzero exit code.
        assert manifest.status != "succeeded"
        assert exit_code != 0

    def test_ambiguous_input_halts_design(self):
        ctx = _ctx(0)
        ctx.research_question = (
            "classification and regression and calibration and huber"
            " accuracy mae study"
        )
        ctx.domain = "machine learning"
        ensure_autonomous_experiment_design(ctx)
        design = ctx.params["autonomous_experiment_design"]
        assert design["status"] == "ambiguous_capability"
