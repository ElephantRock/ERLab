"""Deterministic proof of canonical-current vs release-final paper lifecycle."""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.api.errors import APIError
from backend.api.routes.ideas import router as ideas_router
from backend.api.routes.paper_export import router as paper_export_router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import PaperRevision, Proposal
from backend.pipeline.evaluation.paper_release import (
    PaperReleaseError,
    compute_paper_hash,
    freeze_current_paper,
    load_frozen_revision,
    record_successor_revision_if_released,
)


@pytest.fixture
def env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/paper_release.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def _test_session():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    monkeypatch.setattr("backend.db.database.get_session", _test_session)

    app = FastAPI()

    @app.exception_handler(APIError)
    async def _handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(ideas_router, prefix="/api/v1/ideas")
    app.include_router(paper_export_router, prefix="/api/v1/export")
    client = TestClient(app)

    paper = "# Assured Paper\n\nExact release content.\n"
    paper_hash = compute_paper_hash(paper)
    with _test_session() as s:
        run = crud.create_pipeline_run(s, domain="AI/NLP", status="completed")
        idea = crud.create_idea(
            s,
            title="Release Test",
            problem_statement="p",
            proposed_method="m",
            pipeline_run_id=run.id,
        )
        proposal = Proposal(
            idea_id=idea.id,
            content_md="proposal",
            references_json="[]",
            sections_json="{}",
            paper_md=paper,
            paper_meta_json=json.dumps({
                "status": "ready",
                "paper_evaluation": {
                    "status": "ready",
                    "scope": "paper",
                    "paper_hash": paper_hash,
                    "gates": [{"gate": "provenance", "passed": True}],
                },
            }),
        )
        s.add(proposal)
        s.commit()
        return {
            "Session": Session,
            "session": _test_session,
            "client": client,
            "idea_id": idea.id,
            "proposal_id": proposal.id,
            "paper": paper,
            "paper_hash": paper_hash,
        }


def test_freeze_identifies_exact_ready_revision(env):
    with env["session"]() as s:
        proposal = s.get(Proposal, env["proposal_id"])
        release = freeze_current_paper(s, proposal)
        s.commit()

        assert release["state"] == "frozen"
        assert release["frozen_paper_hash"] == env["paper_hash"]
        revision = s.get(PaperRevision, release["frozen_revision_id"])
        assert revision is not None
        assert revision.paper_md == env["paper"]
        assert revision.paper_hash == env["paper_hash"]
        assert revision.eval_status == "ready"
        assert revision.trigger == "release_freeze"


def test_freeze_is_idempotent_for_same_exact_content(env):
    with env["session"]() as s:
        proposal = s.get(Proposal, env["proposal_id"])
        first = freeze_current_paper(s, proposal)
        second = freeze_current_paper(s, proposal)
        s.commit()

        assert first["frozen_revision_id"] == second["frozen_revision_id"]
        rows = s.execute(
            select(PaperRevision).where(
                PaperRevision.proposal_id == env["proposal_id"],
                PaperRevision.trigger == "release_freeze",
            )
        ).scalars().all()
        assert len(rows) == 1


def test_blocked_or_stale_assurance_cannot_freeze(env):
    with env["session"]() as s:
        proposal = s.get(Proposal, env["proposal_id"])
        meta = json.loads(proposal.paper_meta_json)
        meta["paper_evaluation"]["status"] = "blocked"
        proposal.paper_meta_json = json.dumps(meta)
        s.flush()
        with pytest.raises(PaperReleaseError):
            freeze_current_paper(s, proposal)

    with env["session"]() as s:
        proposal = s.get(Proposal, env["proposal_id"])
        meta = json.loads(proposal.paper_meta_json)
        meta["paper_evaluation"]["status"] = "ready"
        meta["paper_evaluation"]["paper_hash"] = "0" * 64
        proposal.paper_meta_json = json.dumps(meta)
        s.flush()
        with pytest.raises(PaperReleaseError):
            freeze_current_paper(s, proposal)


def test_post_release_successor_does_not_mutate_frozen_revision(env):
    successor = "# Corrected Paper\n\nA later assured correction.\n"
    successor_hash = compute_paper_hash(successor)

    with env["session"]() as s:
        proposal = s.get(Proposal, env["proposal_id"])
        first_release = freeze_current_paper(s, proposal)
        frozen = s.get(PaperRevision, first_release["frozen_revision_id"])
        frozen_text = frozen.paper_md

        successor_revision = record_successor_revision_if_released(
            s,
            proposal,
            successor,
            eval_status="ready",
            gates=[{"gate": "provenance", "passed": True}],
            source="test_correction",
            trigger="post_release_test",
        )
        assert successor_revision is not None
        proposal.paper_md = successor
        meta = json.loads(proposal.paper_meta_json)
        meta["paper_evaluation"] = {
            "status": "ready",
            "scope": "paper",
            "paper_hash": successor_hash,
            "gates": [{"gate": "provenance", "passed": True}],
        }
        proposal.paper_meta_json = json.dumps(meta)
        s.commit()

        # The original release row remains byte-identical and is still the
        # release pointer until a second explicit freeze occurs.
        s.refresh(frozen)
        assert frozen.paper_md == frozen_text == env["paper"]
        meta = json.loads(proposal.paper_meta_json)
        assert meta["release"]["frozen_revision_id"] == first_release["frozen_revision_id"]
        assert meta["release"]["frozen_paper_hash"] == env["paper_hash"]
        assert proposal.paper_md == successor

        second_release = freeze_current_paper(s, proposal)
        s.commit()
        assert second_release["frozen_revision_id"] != first_release["frozen_revision_id"]
        assert second_release["frozen_paper_hash"] == successor_hash
        # Both released versions survive in immutable revision history.
        released = s.execute(
            select(PaperRevision)
            .where(
                PaperRevision.proposal_id == proposal.id,
                PaperRevision.trigger == "release_freeze",
            )
            .order_by(PaperRevision.revision_number)
        ).scalars().all()
        assert [r.paper_hash for r in released] == [env["paper_hash"], successor_hash]


def test_freeze_api_rejects_blocked_and_freezes_ready(env):
    with env["session"]() as s:
        proposal = s.get(Proposal, env["proposal_id"])
        meta = json.loads(proposal.paper_meta_json)
        meta["paper_evaluation"]["status"] = "blocked"
        proposal.paper_meta_json = json.dumps(meta)
        s.commit()

    blocked = env["client"].post(f"/api/v1/ideas/{env['idea_id']}/paper/freeze")
    assert blocked.status_code == 409

    with env["session"]() as s:
        proposal = s.get(Proposal, env["proposal_id"])
        meta = json.loads(proposal.paper_meta_json)
        meta["paper_evaluation"]["status"] = "ready"
        meta["paper_evaluation"]["paper_hash"] = env["paper_hash"]
        proposal.paper_meta_json = json.dumps(meta)
        s.commit()

    frozen = env["client"].post(f"/api/v1/ideas/{env['idea_id']}/paper/freeze")
    assert frozen.status_code == 200
    assert frozen.json()["release"]["state"] == "frozen"


def test_release_export_stays_on_frozen_revision_when_current_advances(env):
    # Freeze v1 through the public lifecycle action.
    response = env["client"].post(f"/api/v1/ideas/{env['idea_id']}/paper/freeze")
    assert response.status_code == 200
    release = response.json()["release"]

    successor = "# Current Candidate\n\nNot yet released.\n"
    with env["session"]() as s:
        proposal = s.get(Proposal, env["proposal_id"])
        record_successor_revision_if_released(
            s,
            proposal,
            successor,
            eval_status="ready",
            gates=[],
            source="test",
            trigger="post_release_test",
        )
        proposal.paper_md = successor
        meta = json.loads(proposal.paper_meta_json)
        meta["paper_evaluation"] = {
            "status": "ready",
            "scope": "paper",
            "paper_hash": compute_paper_hash(successor),
            "gates": [],
        }
        proposal.paper_meta_json = json.dumps(meta)
        s.commit()

    ordinary = env["client"].get(f"/api/v1/export/paper/markdown/{env['idea_id']}")
    assert ordinary.status_code == 200
    assert successor in ordinary.text

    released = env["client"].get(f"/api/v1/export/paper/release/markdown/{env['idea_id']}")
    assert released.status_code == 200
    assert released.text == env["paper"]
    assert released.headers["X-ERLab-Paper-Hash"] == env["paper_hash"]
    assert released.headers["X-ERLab-Revision-Id"] == str(release["frozen_revision_id"])
    assert compute_paper_hash(released.text) == env["paper_hash"]


def test_ordinary_export_remains_available_before_freeze(env):
    ordinary = env["client"].get(f"/api/v1/export/paper/markdown/{env['idea_id']}")
    assert ordinary.status_code == 200
    assert env["paper"] in ordinary.text

    released = env["client"].get(f"/api/v1/export/paper/release/markdown/{env['idea_id']}")
    assert released.status_code == 404


def test_mutation_writers_are_wired_to_release_history_or_existing_revision_history():
    """All production paper writers have an explicit post-release history path."""
    import inspect
    from backend.pipeline import persistence
    from backend.pipeline.evaluation import paper_remediator, targeted_remediator
    from backend.pipeline.experiment import paper_recovery

    assert "record_successor_revision_if_released" in inspect.getsource(persistence)
    assert "record_successor_revision_if_released" in inspect.getsource(targeted_remediator)
    assert "record_successor_revision_if_released" in inspect.getsource(paper_recovery)
    # The Phase-9 remediator already persists the revised paper as an immutable
    # PaperRevision before/alongside promotion; do not replace its established
    # one-attempt revision contract.
    remediation_source = inspect.getsource(paper_remediator.auto_revise_paper)
    assert "_persist_revision" in remediation_source
    assert "PaperRevision" in remediation_source

    from backend.pipeline.stages import PaperSynthesisStage
    evaluation_source = inspect.getsource(PaperSynthesisStage._evaluate_paper)
    assert '"paper_hash": paper_hash' in evaluation_source
