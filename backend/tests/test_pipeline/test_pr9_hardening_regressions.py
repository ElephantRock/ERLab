"""PR #9 review hardening: targeted regression tests.

Each test exercises the exact defect the reviewer identified, not
merely the broader EAD lifecycle. The tests are organized by the
reviewer's hardening categories.
"""

from __future__ import annotations

import asyncio
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

sys.modules.setdefault("chromadb", MagicMock())
sys.modules.setdefault("google.generativeai", MagicMock())

import backend.db.database as db_mod
import backend.pipeline.stages as stages_mod
from backend.db.database import Base
from backend.db.models import (
    ExperimentResult,
    Idea,
    PipelineRun,
    Proposal,
)

# ── Sigmoid calibration math ──────────────────────────────────────────────


class TestSigmoidCalibration:
    """Verify the corrected multiclass sigmoid calibration."""

    def test_positive_class_calibrated(self):
        """The positive-class probability is sigmoid(a*p + b)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "analysis",
            "experiments/tabular_calibration_selective_v1/analysis.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        probs = {"a": 0.6, "b": 0.3, "c": 0.1}
        result = mod.apply_sigmoid_calibration(
            probs, a=2.0, b=-1.0,
            positive_class="a",
        )
        expected_a = mod._sigmoid(2.0 * 0.6 + (-1.0))
        assert abs(result["a"] - expected_a) < 1e-12

    def test_other_classes_redistributed_proportionally(self):
        """Non-positive classes keep their original ratio."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "analysis",
            "experiments/tabular_calibration_selective_v1/analysis.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        probs = {"a": 0.6, "b": 0.3, "c": 0.1}
        result = mod.apply_sigmoid_calibration(
            probs, a=2.0, b=-1.0,
            positive_class="a",
        )
        # b:c ratio should match original 3:1
        assert abs(result["b"] / result["c"] - 3.0) < 1e-9

    def test_probabilities_sum_to_one(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "analysis",
            "experiments/tabular_calibration_selective_v1/analysis.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        probs = {"a": 0.5, "b": 0.3, "c": 0.2}
        result = mod.apply_sigmoid_calibration(
            probs, a=1.5, b=0.5,
            positive_class="a",
        )
        assert abs(sum(result.values()) - 1.0) < 1e-12

    def test_prediction_is_deterministic(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "analysis",
            "experiments/tabular_calibration_selective_v1/analysis.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        probs = {"a": 0.6, "b": 0.3, "c": 0.1}
        r1 = mod.apply_sigmoid_calibration(
            probs, a=2.0, b=-1.0,
            positive_class="a",
        )
        r2 = mod.apply_sigmoid_calibration(
            probs, a=2.0, b=-1.0,
            positive_class="a",
        )
        assert r1 == r2


# ── Entrypoint containment ────────────────────────────────────────────────


class TestEntrypointContainment:
    """Verify execute_experiment_spec rejects unsafe paths."""

    @pytest.mark.asyncio
    async def test_absolute_entrypoint_rejected(self, tmp_path):
        from backend.pipeline.experiment.empirical_runner import (
            execute_experiment_spec,
        )
        from backend.pipeline.experiment.specification import (
            ExperimentSpec,
        )
        spec = ExperimentSpec(
            spec_id="test-abs",
            description="t",
            dataset_name="iris",
            dataset_version="1.0",
            dataset_raw_filename="iris_raw.csv",
            dataset_raw_sha256="x" * 64,
            split_method="s",
            train_fraction=0.8,
            test_fraction=0.2,
            random_seed=42,
            analysis_entrypoint=str(tmp_path / "evil.py"),
            analysis_method="t",
            declared_metrics=["accuracy"],
            metric_directions={},
            tolerances={},
            output_artifacts=[],
            research_question="t",
        )
        manifest, _, stderr, exit_code, _ = (
            await execute_experiment_spec(
                spec, tmp_path / "out", 10.0,
            )
        )
        assert exit_code != 0
        assert "absolute" in stderr.lower() or (
            "not project-relative" in stderr.lower()
        )

    @pytest.mark.asyncio
    async def test_traversal_rejected(self, tmp_path):
        from backend.pipeline.experiment.empirical_runner import (
            execute_experiment_spec,
        )
        from backend.pipeline.experiment.specification import (
            ExperimentSpec,
        )
        spec = ExperimentSpec(
            spec_id="test-trav",
            description="t",
            dataset_name="iris",
            dataset_version="1.0",
            dataset_raw_filename="iris_raw.csv",
            dataset_raw_sha256="x" * 64,
            split_method="s",
            train_fraction=0.8,
            test_fraction=0.2,
            random_seed=42,
            analysis_entrypoint="../../../etc/passwd",
            analysis_method="t",
            declared_metrics=["accuracy"],
            metric_directions={},
            tolerances={},
            output_artifacts=[],
            research_question="t",
        )
        manifest, _, _, exit_code, _ = (
            await execute_experiment_spec(
                spec, tmp_path / "out", 10.0,
            )
        )
        assert exit_code != 0

    @pytest.mark.asyncio
    async def test_valid_relative_entrypoint_succeeds(
        self, tmp_path,
    ):
        """A valid checked-in entrypoint executes."""
        from backend.pipeline.experiment.empirical_runner import (
            execute_experiment_spec,
        )
        from backend.pipeline.experiment.specification import (
            ExperimentSpec,
        )
        spec = ExperimentSpec(
            spec_id="test-valid",
            description="t",
            dataset_name="iris",
            dataset_version="1.0.0",
            dataset_raw_filename="iris_raw.csv",
            dataset_raw_sha256=(
                "1091a0dfd033acb7733af503637b2c7db8818"
                "ebe67ec8ccd5a4d4d5e57f5914f"
            ),
            split_method="s",
            train_fraction=0.8,
            test_fraction=0.2,
            random_seed=42,
            analysis_entrypoint=(
                "experiments/tabular_calibration"
                "_selective_v1/analysis.py"
            ),
            analysis_method="t",
            declared_metrics=["baseline_accuracy"],
            metric_directions={
                "baseline_accuracy": "higher_better",
            },
            tolerances={"baseline_accuracy": 0.001},
            output_artifacts=["metrics.json"],
            research_question="t",
        )
        manifest, _, _, exit_code, _ = (
            await execute_experiment_spec(
                spec, tmp_path / "out", 300.0,
            )
        )
        assert exit_code == 0
        assert manifest.status == "succeeded"


# ── Proposal identity ─────────────────────────────────────────────────────


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


def _seed_two_proposals(engine):
    """Seed a run with 2 ideas + 2 proposals. Return (run_id,
    [(idea_id_0, prop_id_0), (idea_id_1, prop_id_1)])."""
    Session = sessionmaker(
        bind=engine, expire_on_commit=False,
    )
    session = Session()
    run = PipelineRun(
        run_id_str="run_multi", domain="ML",
        status="running", config_json="{}",
        stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()

    pairs = []
    for i in range(2):
        idea = Idea(
            title=f"Idea {i}",
            problem_statement="P",
            proposed_method="M",
            expected_contributions="C",
            domain="ML",
            novelty_score=0.5,
            feasibility_score=0.8 - i * 0.1,
            overall_score=0.8 - i * 0.1,
            pipeline_run_id=run.id,
        )
        session.add(idea)
        session.commit()
        proposal = Proposal(
            idea_id=idea.id, content_md=f"prop {i}",
        )
        session.add(proposal)
        session.commit()
        pairs.append((idea.id, proposal.id, idea.title))

    session.close()
    return run.id, pairs


@contextmanager
def _patched_session(engine):
    test_sf = sessionmaker(
        bind=engine, expire_on_commit=False,
    )

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


class TestProposalIdentity:
    def test_selected_not_newest(self):
        """When the selected proposal is NOT the newest one in
        the run, the ExperimentResult must link to the selected
        proposal, not the newest."""
        engine = _make_engine()
        run_id, pairs = _seed_two_proposals(engine)
        # pairs[1] is newer (higher id). Select pairs[0] instead.
        selected_idea_id = pairs[0][0]
        selected_prop_id = pairs[0][1]
        selected_title = pairs[0][2]

        from backend.pipeline.generation.models import (
            ResearchIdea,
        )
        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import (
            ExperimentExecutionStage,
            StageContext,
        )

        ctx = StageContext(
            result=PipelineResult(),
            domain="ML",
            db_run_id=run_id,
        )
        ctx.result.ideas = [
            ResearchIdea(
                title=selected_title,
                problem_statement="P",
                proposed_method="M",
                expected_contributions="C",
                novelty_rationale="N",
                evaluation_approach="accuracy",
                domain="ML",
                round_generated=1,
                score=0.8,
                supporting_papers=[],
                source_gap_ids=[],
            ),
        ]

        from backend.pipeline.experiment.manifest import (
            AnalysisSpec,
            DatasetIdentity,
            ExperimentManifest,
            SplitSpec,
        )

        manifest = ExperimentManifest(
            experiment_spec_id="test",
            status="succeeded",
            dataset=DatasetIdentity(
                name="iris", version="1",
                source="", license="",
                relative_path="",
                raw_sha256="abc",
            ),
            split=SplitSpec(
                method="s", train_fraction=0.8,
                test_fraction=0.2, random_seed=42,
            ),
            analysis=AnalysisSpec(
                entrypoint=(
                    "experiments/tabular_calibration"
                    "_selective_v1/analysis.py"
                ),
                code_sha256="",
                command="",
                method="lr",
                declared_metrics=["accuracy"],
            ),
            results={"accuracy": 0.9},
        )

        stage = ExperimentExecutionStage()
        with _patched_session(engine):
            asyncio.run(stage._persist_experiment(
                ctx, 0, manifest,
                "", "", 0, 0.1,
                markers_for_execution=[],
            ))

        Session = sessionmaker(bind=engine)
        session = Session()
        rows = session.execute(
            select(ExperimentResult).where(
                ExperimentResult.proposal_id
                == selected_prop_id,
            )
        ).scalars().all()
        assert len(rows) == 1, (
            "Expected ExperimentResult linked to selected"
            f" proposal {selected_prop_id}, got"
            f" {len(rows)} rows"
        )
        assert rows[0].idea_id == selected_idea_id
        session.close()
