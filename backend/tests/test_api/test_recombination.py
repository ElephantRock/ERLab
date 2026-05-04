"""Tests for POST /recombination/propose endpoint (BATCH-65/TASK-02)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.errors import APIError
from backend.api.routes.recombination import router
from backend.db.models import Idea


# ── Test app setup ──────────────────────────────────────────────


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router)
    return app


def _mock_idea(idea_id: int, run_id: int, title: str, score: float = 0.8) -> Idea:
    """Create a mock Idea DB object."""
    idea = MagicMock(spec=Idea)
    idea.id = idea_id
    idea.title = title
    idea.problem_statement = f"Problem for {title}"
    idea.proposed_method = f"Using deep learning and transformers for {title.lower()}"
    idea.expected_contributions = f"Contributions for {title}"
    idea.domain = "AI/NLP"
    idea.overall_score = score
    idea.novelty_score = score
    idea.feasibility_score = score * 10
    idea.source_gap_ids = None
    idea.pipeline_run_id = run_id
    return idea


def _mock_session():
    """Create a mock DB session context manager."""
    mock_session = MagicMock()
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_session)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm, mock_session


# ── TEST-65-02-01: POST /recombination/propose returns recombined ideas ──


def test_65_02_01_propose_returns_recombined_ideas():
    """Integration: POST /recombination/propose returns recombined ideas."""
    # Ideas for run 1
    ideas_run_1 = [
        _mock_idea(1, run_id=1, title="Idea A", score=0.9),
        _mock_idea(2, run_id=1, title="Idea B", score=0.7),
    ]
    # Ideas for run 2
    ideas_run_2 = [
        _mock_idea(3, run_id=2, title="Idea C", score=0.85),
        _mock_idea(4, run_id=2, title="Idea D", score=0.6),
    ]

    mock_cm, mock_session = _mock_session()

    # Mock the stored idea returned by create_idea
    stored_idea = MagicMock()
    stored_idea.id = 100
    stored_idea.title = "Recombined Idea"

    def fake_get_ideas(session, run_id):
        if run_id == 1:
            return ideas_run_1
        return ideas_run_2

    # Mock IdeaRecombinator.recombine to return a deterministic child
    mock_child = MagicMock()
    mock_child.title = "Recombined Novel Idea"
    mock_child.problem_statement = "Combined problem"
    mock_child.proposed_method = "Combined method"
    mock_child.expected_contributions = "Combined contributions"
    mock_child.parent_idea_ids = [1, 3]

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.get_ideas_for_run", side_effect=fake_get_ideas), \
         patch("backend.providers.provider_factory.create_provider") as mock_prov, \
         patch("backend.pipeline.generation.recombination.IdeaRecombinator.recombine", new_callable=AsyncMock, return_value=mock_child), \
         patch("backend.db.crud.create_idea", return_value=stored_idea):
        mock_prov.return_value = MagicMock()

        client = TestClient(_make_app())
        resp = client.post(
            "/propose",
            json={"run_ids": [1, 2], "max_ideas": 5},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert "recombined_ideas" in body
    assert "method_dna" in body
    assert len(body["recombined_ideas"]) == 1  # 1 pair from 2 runs
    assert body["recombined_ideas"][0]["source_idea_ids"] == [1, 3]

    # Verify method DNA contains records for both parents
    assert len(body["method_dna"]) == 2
    dna_ids = {d["idea_id"] for d in body["method_dna"]}
    assert 1 in dna_ids
    assert 3 in dna_ids


# ── TEST-65-02-02: Returns 400 if run has <2 ideas (HB-01) ──────


def test_65_02_02_returns_400_if_run_has_fewer_than_2_ideas():
    """Integration: Returns 400 if a run has fewer than 2 ideas (HB-01)."""
    # Run 1 has 2 ideas (OK), run 2 has only 1 idea (should fail)
    ideas_run_1 = [
        _mock_idea(1, run_id=1, title="Idea A", score=0.9),
        _mock_idea(2, run_id=1, title="Idea B", score=0.7),
    ]
    ideas_run_2 = [
        _mock_idea(3, run_id=2, title="Idea C", score=0.85),
    ]

    mock_cm, mock_session = _mock_session()

    def fake_get_ideas(session, run_id):
        if run_id == 1:
            return ideas_run_1
        return ideas_run_2

    with patch("backend.db.database.get_session", return_value=mock_cm), \
         patch("backend.db.crud.get_ideas_for_run", side_effect=fake_get_ideas):
        client = TestClient(_make_app())
        resp = client.post(
            "/propose",
            json={"run_ids": [1, 2], "max_ideas": 5},
        )

    assert resp.status_code == 400
    body = resp.json()
    assert "error" in body
    assert "Run 2 has 1 idea" in body["error"]["message"]
