"""Regression (run 2713, rev 24): the cold repair route read the frozen
source map from meta["full_paper"]["source_map"] — the in-memory proposal
shape. The persisted paper_meta_json is the flat dict written by
_extract_paper_artifact, which has source_map at the TOP level and no
full_paper key at all. The route therefore passed an empty source map
into the evidence invariants, every SOURCE marker in a revision was
falsely "invented", and no cold revision could ever be promoted.

Invokes the actual repair_paper() route (EAD-4A v3 pattern) and asserts
the persisted flat source_map reaches auto_revise_paper.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, event
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

FLAT_SOURCE_MAP = [
    {"marker": "SOURCE-1", "marker_index": 1, "source_id": 11,
     "mapping_status": "mapped"},
    {"marker": "SOURCE-2", "marker_index": 2, "source_id": 12,
     "mapping_status": "mapped"},
    {"marker": "SOURCE-3", "marker_index": 3, "source_id": 13,
     "mapping_status": "mapped"},
]


def _manifest(spec_id: str, dataset: str) -> dict:
    return {
        "experiment_spec_id": spec_id,
        "status": "succeeded",
        "dataset": {"name": dataset},
        "results": {
            f"{dataset}_accuracy": 0.9,
            f"{dataset}_baseline_accuracy": 0.8,
        },
        "result_artifacts": [
            {"artifact_type": "metrics", "filename": "metrics.json",
             "sha256": "a" * 8},
        ],
    }


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
        db_mod._get_engine = lambda: engine


def _seed(engine, meta_builder) -> int:
    """Seed run/idea/proposal + two experiment rows. The proposal's
    paper_meta_json is built by meta_builder(source_map_entries, paper_hash)
    so tests can choose the flat or nested shape."""
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    run = PipelineRun(
        run_id_str="run_pr9c", domain="ML", status="completed",
        config_json="{}", stages_completed="[]",
        provenance_version="provenance_v1",
    )
    session.add(run)
    session.commit()
    idea = Idea(
        title="Cold Route Source Map",
        problem_statement="p", proposed_method="m",
        expected_contributions="c", domain="ML",
        novelty_score=0.5, feasibility_score=0.8, overall_score=0.8,
        pipeline_run_id=run.id,
    )
    session.add(idea)
    session.commit()
    proposal = Proposal(idea_id=idea.id, content_md="test")
    session.add(proposal)
    session.commit()

    for spec_id, ds in (
        ("auto-x-iris", "iris"),
        ("auto-x-wine", "wine_quality"),
    ):
        session.add(ExperimentResult(
            idea_id=idea.id, proposal_id=proposal.id,
            code_md="", stdout="", stderr="",
            exit_code=0, success=True,
            manifest_json=json.dumps(_manifest(spec_id, ds)),
        ))
    session.commit()

    paper_md = (
        "# Study\n\n0.9 [RESULT-1]\n\nCites [SOURCE-1] and [SOURCE-2].\n"
    )
    paper_hash = hashlib.sha256(paper_md.encode()).hexdigest()
    meta = meta_builder(paper_hash)
    proposal.paper_md = paper_md
    proposal.paper_meta_json = json.dumps(meta)
    session.commit()
    idea_id = idea.id
    session.close()
    return idea_id


def _flat_meta(paper_hash: str) -> dict:
    """The persisted DB shape (persistence._extract_paper_artifact):
    flat keys, top-level source_map, NO full_paper key."""
    return {
        "status": "ready",
        "paper_evaluation": {
            "status": "blocked",
            "paper_hash": paper_hash,
            "blocking_reasons": ["numeric_fidelity: test"],
            "gates": [],
        },
        "source_map": FLAT_SOURCE_MAP,
        "result_markers": [],
        "autonomous_experiment_design": {
            "status": "designed",
            "capability_id": "tabular_calibration_selective_v1",
            "selected_proposal_idx": 0,
            "research_question": "q",
            "diagnostics": [],
            "specs": [
                {"experiment_spec_id": "auto-x-iris",
                 "dataset": {"name": "iris"}},
                {"experiment_spec_id": "auto-x-wine",
                 "dataset": {"name": "wine_quality"}},
            ],
        },
    }


def _nested_meta(paper_hash: str) -> dict:
    """The legacy in-memory proposal shape (nested full_paper)."""
    meta = _flat_meta(paper_hash)
    meta.pop("source_map")
    meta["full_paper"] = {"source_map": FLAT_SOURCE_MAP}
    return meta


def _invoke_route(idea_id: int) -> dict:
    captured = {}

    async def _stub_revise(**kwargs):
        captured.update(kwargs)
        return RemediationResult(
            success=False, promoted=False, revision_number=1,
            eval_status="blocked", gates=[],
            blocking_reasons=["stub"],
            original_paper_hash="x", revised_paper_hash="y",
            invariant_violations=[],
        )

    import contextlib

    with patch(
        "backend.pipeline.evaluation.paper_remediator.auto_revise_paper",
        new=_stub_revise,
    ):
        from backend.api.routes.ideas import repair_paper

        with contextlib.suppress(Exception):
            asyncio.run(repair_paper(idea_id))
    return captured


class TestColdRouteSourceMap:
    def test_persisted_flat_source_map_reaches_remediator(self):
        engine = _make_engine()
        with _patched_session(engine):
            idea_id = _seed(engine, _flat_meta)
            captured = _invoke_route(idea_id)

        assert captured, "route must reach auto_revise_paper"
        assert captured.get("source_map") == FLAT_SOURCE_MAP, (
            "the persisted top-level source_map must reach the"
            " remediator — an empty map makes every SOURCE marker"
            " falsely 'invented' and blocks all cold promotion"
        )

    def test_legacy_nested_shape_still_supported(self):
        engine = _make_engine()
        with _patched_session(engine):
            idea_id = _seed(engine, _nested_meta)
            captured = _invoke_route(idea_id)

        assert captured.get("source_map") == FLAT_SOURCE_MAP

    def test_flat_markers_reconstruct_both_datasets(self):
        """Full cold-recovery sanity on the flat shape: markers from
        both datasets reach the remediator."""
        engine = _make_engine()
        with _patched_session(engine):
            idea_id = _seed(engine, _flat_meta)
            captured = _invoke_route(idea_id)

        markers = captured.get("result_markers", [])
        datasets = {m.metric_name.split(".")[0] for m in markers}
        assert datasets == {"iris", "wine_quality"}
        assert len(markers) == 4


class TestColdReEvaluationIntent:
    """Regression (run 2713, third repair attempt): the post-remediation
    evaluation built its StageContext with a generic two-word domain and
    NO research question, so the scope gate scored the promoted paper
    against a near-empty intent and blocked on a 0.00-overlap reading.
    The re-evaluation context must carry the frozen research question
    from the persisted design and the domain from the run row."""

    def test_re_eval_context_carries_persisted_question_and_domain(self):
        import contextlib
        from unittest.mock import patch as _patch

        engine = _make_engine()

        def _meta_with_run_domain(paper_hash: str) -> dict:
            meta = _flat_meta(paper_hash)
            meta["autonomous_experiment_design"]["research_question"] = (
                "How does calibration affect selective classification?"
            )
            return meta

        eval_ctxs = []

        async def _stub_evaluate(self, ctx, proposal_obj, meta, idx):
            eval_ctxs.append(ctx)
            return None

        with _patched_session(engine):
            # Seed with a run domain the route must recover.
            idea_id = _seed(engine, _meta_with_run_domain)
            sf = sessionmaker(bind=engine)
            s = sf()
            run = s.query(PipelineRun).first()
            run.domain = "Robust ML under distribution shift"
            s.commit()
            s.close()

            async def _stub_revise(**kwargs):
                from backend.pipeline.evaluation.paper_remediator import (
                    RemediationResult,
                )
                return RemediationResult(
                    success=True, promoted=True, revision_number=1,
                    eval_status="ready", gates=[],
                    blocking_reasons=[],
                    original_paper_hash="x",
                    revised_paper_hash="y",
                    invariant_violations=[],
                )

            with _patch(
                "backend.pipeline.evaluation.paper_remediator"
                ".auto_revise_paper",
                new=_stub_revise,
            ), _patch(
                "backend.providers.provider_factory.create_provider",
                return_value=MagicMock(),
            ), _patch(
                "backend.pipeline.stages.PaperSynthesisStage"
                "._evaluate_paper",
                new=_stub_evaluate,
            ):
                from backend.api.routes.ideas import repair_paper

                with contextlib.suppress(Exception):
                    asyncio.run(repair_paper(idea_id))

        assert eval_ctxs, "route must run the post-remediation evaluation"
        ctx = eval_ctxs[0]
        assert ctx.research_question == (
            "How does calibration affect selective classification?"
        )
        assert ctx.domain == "Robust ML under distribution shift"
