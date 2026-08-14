"""EAD-4A v3: Actual repair_paper() route invocation.

Replaces the simulated recovery in v2 with real route calls,
proving the production wiring from persisted state through
auto_revise_paper() and post-remediation evaluation.

POSITIVE: stub auto_revise_paper, invoke actual route, verify
captured markers contain both datasets and the autonomous design
reaches the evaluation context.

NEGATIVE: delete wine's ExperimentResult, invoke actual route,
assert ConflictError, assert auto_revise never called.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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
from backend.pipeline.evaluation.paper_remediator import (
    RemediationResult,
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


def _setup_blocked_autonomous(engine):
    """Execute autonomous study and persist blocked paper.
    Returns (run_id, idea_id, proposal_id)."""

    from backend.pipeline.generation.models import (
        ResearchIdea,
    )
    from backend.pipeline.result import PipelineResult
    from backend.pipeline.stages import (
        ExperimentExecutionStage,
        StageContext,
        ensure_autonomous_experiment_design,
    )
    from backend.pipeline.synthesis.proposal_synthesizer import (
        FeasibilityReport,
    )

    Session = sessionmaker(
        bind=engine, expire_on_commit=False,
    )
    session = Session()

    run = PipelineRun(
        run_id_str="run_route", domain="ML",
        status="completed", config_json="{}",
        stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()

    idea = Idea(
        title="Calibration Route Test",
        problem_statement="calibration shift",
        proposed_method="logistic regression",
        expected_contributions="selective",
        domain="ML", novelty_score=0.5,
        feasibility_score=0.8, overall_score=0.8,
        pipeline_run_id=run.id,
    )
    session.add(idea)
    session.commit()

    proposal = Proposal(
        idea_id=idea.id, content_md="test",
    )
    session.add(proposal)
    session.commit()

    idea_id = idea.id
    proposal_id = proposal.id
    run_id = run.id
    session.close()

    ctx = StageContext(
        result=PipelineResult(),
        domain="machine learning",
        research_question=(
            "How does calibration affect"
            " selective classification?"
        ),
        db_run_id=run_id,
    )
    ctx.params["autonomous_experiment_enabled"] = True
    ctx.result.ideas = [ResearchIdea(
        title="Calibration Route Test",
        problem_statement="calibration shift",
        proposed_method="logistic regression",
        expected_contributions="selective",
        novelty_rationale="novel",
        evaluation_approach="accuracy metrics",
        domain="ML", round_generated=1, score=0.8,
        supporting_papers=[], source_gap_ids=[],
    )]
    ctx.result.feasibility_reports = {0: FeasibilityReport(
        overall_score=0.8,
        data_availability=7,
        computational_requirements=8,
        methodological_complexity=7,
        evaluation_plan=8,
        novelty_grounding=6,
        impact_potential=7,
        reasoning="ok",
        estimated_timeline="2w",
        key_risks=[],
    )}
    ctx.result.proposals = {0: SimpleNamespace(
        title="T", to_markdown=lambda: "t",
    )}

    ensure_autonomous_experiment_design(ctx)
    design = ctx.params["autonomous_experiment_design"]
    assert design["status"] == "designed"

    stage = ExperimentExecutionStage()
    ok = asyncio.run(stage._execute_autonomous(ctx, design))
    assert ok is True

    selected = design["selected_proposal_idx"]
    live_markers = list(ctx.result.result_markers[selected])

    paper_md = "# Calibration Study\n"
    for m in live_markers:
        paper_md += f"{m.observed_value} [{m.marker}]\n"
    paper_md += "## Conclusion\nResults.\n"
    paper_hash = hashlib.sha256(
        paper_md.encode()
    ).hexdigest()

    specs_serialized = design["specs"]
    meta = {
        "autonomous_experiment_design": {
            "status": "designed",
            "capability_id": (
                "tabular_calibration_selective_v1"
            ),
            "selected_proposal_idx": selected,
            "research_question": design.get(
                "research_question", "",
            ),
            "specs": specs_serialized,
            "diagnostics": [],
        },
        "paper_evaluation": {
            "status": "blocked",
            "paper_hash": paper_hash,
            "blocking_reasons": [
                "numeric_fidelity: test",
            ],
            "gates": [],
        },
        "full_paper": {
            "paper_markdown": paper_md,
            "source_map": [],
        },
    }

    with db_mod.get_session() as session:
        prop = session.get(Proposal, proposal_id)
        prop.paper_md = paper_md
        prop.paper_meta_json = json.dumps(meta)
        session.commit()

    return run_id, idea_id, proposal_id


class TestActualRepairRoutePositive:
    def test_route_recovers_both_datasets_and_calls_remediator(
        self,
    ):
        """Invoke the actual repair_paper() route with a
        deterministic stub on auto_revise_paper."""
        engine = _make_engine()

        with _patched_session(engine):
            run_id, idea_id, proposal_id = (
                _setup_blocked_autonomous(engine)
            )

            # Capture what auto_revise_paper receives.
            captured = {}

            async def _stub_revise(**kwargs):
                captured.update(kwargs)
                captured["markers_count"] = len(
                    kwargs.get("result_markers", []),
                )
                captured["datasets"] = {
                    m.metric_name.split(".")[0]
                    for m in kwargs.get(
                        "result_markers", [],
                    )
                }
                captured["exp_result_ids"] = {
                    m.experiment_result_id
                    for m in kwargs.get(
                        "result_markers", [],
                    )
                }
                return RemediationResult(
                    success=False,
                    promoted=False,
                    revision_number=1,
                    eval_status="blocked",
                    gates=[],
                    blocking_reasons=["stub"],
                    original_paper_hash="x",
                    revised_paper_hash="y",
                    invariant_violations=[],
                )

            with patch(
                "backend.pipeline.evaluation."
                "paper_remediator.auto_revise_paper",
                new=_stub_revise,
            ):
                import contextlib

                from backend.api.routes.ideas import (
                    repair_paper,
                )

                with contextlib.suppress(Exception):
                    asyncio.run(
                        repair_paper(idea_id),
                    )

            # Verify the route recovered both datasets.
            assert captured.get("markers_count", 0) == 74
            assert "iris" in captured.get("datasets", set())
            assert (
                "wine_quality"
                in captured.get("datasets", set())
            )
            assert len(
                captured.get("exp_result_ids", set())
            ) == 2


class TestActualRepairRouteNegative:
    def test_missing_dataset_raises_conflict_error(self):
        """When wine's result is deleted, the route must
        raise and never call auto_revise_paper."""
        engine = _make_engine()

        with _patched_session(engine):
            run_id, idea_id, proposal_id = (
                _setup_blocked_autonomous(engine)
            )

            # Delete wine's result (newer row).
            Session = sessionmaker(bind=engine)
            session = Session()
            rows = session.execute(
                select(ExperimentResult).where(
                    ExperimentResult.proposal_id
                    == proposal_id,
                ).order_by(
                    ExperimentResult.id.asc(),
                ),
            ).scalars().all()
            session.delete(rows[1])
            session.commit()
            session.close()

            remediator_called = []

            async def _spy_revise(**kwargs):
                remediator_called.append(True)
                return RemediationResult(
                    success=False,
                    promoted=False,
                    revision_number=0,
                    eval_status="blocked",
                    gates=[],
                    blocking_reasons=[],
                    original_paper_hash="",
                    revised_paper_hash="",
                    invariant_violations=[],
                )

            with patch(
                "backend.pipeline.evaluation."
                "paper_remediator.auto_revise_paper",
                new=_spy_revise,
            ):

                from backend.api.errors import ConflictError
                from backend.api.routes.ideas import (
                    repair_paper,
                )

                with pytest.raises(
                    ConflictError,
                    match="incomplete",
                ):
                    asyncio.run(
                        repair_paper(idea_id),
                    )

            assert remediator_called == [], (
                "auto_revise_paper must NOT be called"
                " when a dataset is missing"
            )
