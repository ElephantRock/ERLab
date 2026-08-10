"""Phase 2 2G controlled integration scenario.

Extends the Phase 1 controlled integration to cover the full trust & sources
review workflow (spec 2G "Controlled integration scenario" steps 1-10):

  1. Create a run with a persisted research question.
  2. Persist a non-empty paper with references and citation audit.
  3. Retrieve the paper and Trust & Sources payload.
  4. Verify paper and proposal evaluations remain distinct.
  5. Review one source as accepted.
  6. Flag one source.
  7. Mark one source exclude_on_next_revision.
  8. Reload the API and verify all decisions persist.
  9. Verify human-review status is completed_with_flags.
  10. Verify the paper content and identity are unchanged.

No live external provider is required.
"""

from __future__ import annotations

import json
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.api.errors import APIError as _APIError
from backend.api.routes.review import router as review_router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import Proposal

pytestmark = pytest.mark.integration

RESEARCH_QUESTION = (
    "How can graph-based reasoning and neuro-symbolic methods be combined "
    "to improve the verifiability of language-model reasoning?"
)


@pytest.fixture
def e2e_env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/phase2_e2e.db")
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

    @app.exception_handler(_APIError)
    async def _handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(review_router, prefix="/api/v1/ideas")
    client = TestClient(app)

    # Seed: run + research question + idea + proposal with paper + refs + evals.
    with _test_session() as s:
        run = crud.create_pipeline_run(s, domain="AI/NLP", status="completed")
        run.config_json = json.dumps({"research_question": RESEARCH_QUESTION})
        s.commit()
        idea = crud.create_idea(
            s,
            title="Combining graph reasoning and neuro-symbolic methods",
            problem_statement="p",
            proposed_method="m",
            pipeline_run_id=run.id,
        )
        s.commit()
        proposal = Proposal(
            idea_id=idea.id,
            content_md="proposal",
            references_json=json.dumps([
                {"raw": "Smith, J. (2024). Graph-of-Thought. AAAI."},
                {"raw": "Jones, K. (2023). Neuro-symbolic reasoning."},
                {"raw": "Lee, M. (2025). Verifiable LLM reasoning."},
            ]),
            sections_json=json.dumps({
                "related_work": "See [1] and [2].",
            }),
            paper_md="# Paper\n\n## Intro\n\nSee [1], [2], [3].\n",
            paper_meta_json=json.dumps({
                "status": "ready",
                "paper_evaluation": {
                    "status": "ready",
                    "scope": "paper",
                    "dimensions": {"novelty": {"score": 0.8, "justification": "novel"}},
                    "evaluated_object": "final_paper",
                },
            }),
            proposal_evaluation_json=json.dumps({"novelty": {"score": 0.6, "justification": "proposal"}}),
        )
        s.add(proposal)
        s.commit()
        idea_id = idea.id

    return {"client": client, "idea_id": idea_id, "Session": Session}


def test_phase2_end_to_end_trust_and_sources_review(e2e_env):
    client = e2e_env["client"]
    idea_id = e2e_env["idea_id"]

    # 3. Retrieve the Trust & Sources payload.
    r = client.get(f"/api/v1/ideas/{idea_id}/review")
    assert r.status_code == 200, r.text
    body = r.json()
    sources = body["sources"]
    assert len(sources) == 3

    # 4. Paper and proposal evaluations remain distinct.
    pe = body["automated_checks"]["paper_evaluation"]
    pre = body["automated_checks"]["proposal_evaluation"]
    assert pe["scope"] == "paper"
    assert pre["scope"] == "proposal"
    assert pe["dimensions"]["novelty"]["score"] != pre["dimensions"]["novelty"]["score"]

    # 5. Review source 1 as accepted.
    h1 = sources[0]["source_ref_hash"]
    d1 = client.post(
        f"/api/v1/ideas/{idea_id}/review/sources/decisions",
        json={"source_ref_hash": h1, "decision": "accepted"},
    )
    assert d1.status_code == 200

    # 6. Flag source 2.
    h2 = sources[1]["source_ref_hash"]
    client.post(
        f"/api/v1/ideas/{idea_id}/review/sources/decisions",
        json={"source_ref_hash": h2, "decision": "flagged"},
    )

    # 7. Mark source 3 exclude_on_next_revision.
    h3 = sources[2]["source_ref_hash"]
    client.post(
        f"/api/v1/ideas/{idea_id}/review/sources/decisions",
        json={"source_ref_hash": h3, "decision": "exclude_on_next_revision"},
    )

    # 8. Reload the API and verify all decisions persist.
    r2 = client.get(f"/api/v1/ideas/{idea_id}/review")
    body2 = r2.json()
    src_by_hash = {s["source_ref_hash"]: s for s in body2["sources"]}
    assert src_by_hash[h1]["human_decision"]["decision"] == "accepted"
    assert src_by_hash[h2]["human_decision"]["decision"] == "flagged"
    assert src_by_hash[h3]["human_decision"]["decision"] == "exclude_on_next_revision"

    # 9. Human-review status is completed_with_flags.
    assert body2["human_review"]["status"] == "completed_with_flags"
    assert body2["human_review"]["reviewed_sources"] == 3
    assert body2["human_review"]["flagged_or_excluded"] == 2  # flagged + excluded

    # 10. Paper content and identity unchanged (immutability rule).
    # The paper evaluation in the review payload is identical to the original.
    assert body2["automated_checks"]["paper_evaluation"] == body["automated_checks"]["paper_evaluation"]
    # And the paper_md on the Proposal row is unchanged.
    with e2e_env["Session"]() as s:
        proposal = s.execute(select(Proposal).where(Proposal.idea_id == idea_id)).scalar_one()
        assert "# Paper" in proposal.paper_md
        assert "[1], [2], [3]" in proposal.paper_md  # original content intact


def test_phase2_end_to_end_no_decision_means_not_started(e2e_env):
    """Before any decisions, the human-review status is not_started."""
    client = e2e_env["client"]
    idea_id = e2e_env["idea_id"]
    r = client.get(f"/api/v1/ideas/{idea_id}/review")
    assert r.json()["human_review"]["status"] == "not_started"
