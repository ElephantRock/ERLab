"""Phase 5 / 5B.1 — regression test: experiments.py await bug fix.

The `POST /ideas/{id}/run-experiment` endpoint called `generator.generate(candidate)`
without `await`, passing a coroutine object as `code` to the sandbox runner. This
test proves the endpoint now correctly awaits the async generate call and produces
a real ExperimentResult row.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.errors import APIError
from backend.api.routes.experiments import router
from backend.db import crud
from backend.db.database import Base
from backend.db.models import Idea, PipelineRun, ExperimentResult

pytestmark = pytest.mark.slow


@pytest.fixture
def app_env(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/exp_test.db")
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
    async def _h(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router)
    client = TestClient(app)

    seed_session = Session()
    try:
        run = PipelineRun(status="completed", provenance_version="provenance_v1")
        seed_session.add(run)
        seed_session.flush()
        idea = Idea(
            title="Test Empirical Idea",
            problem_statement="Test problem",
            proposed_method="Logistic regression on a tabular dataset",
            pipeline_run_id=run.id,
        )
        seed_session.add(idea)
        seed_session.commit()
        idea_id = idea.id
    finally:
        seed_session.close()

    # Enable experiments — patch at the import site in experiments.py
    mock_settings = type("S", (), {
        "experiment_enabled": True,
        "experiment_default_timeout": 30.0,
        "experiment_max_code_size": 10000,
    })()
    monkeypatch.setattr("backend.api.routes.experiments.get_settings", lambda: mock_settings)

    return client, idea_id


def test_run_idea_experiment_produces_real_result(app_env):
    """POST /ideas/{id}/run-experiment must produce a real ExperimentResult.

    Before the fix, the endpoint passed a coroutine as `code`, causing
    execution failure. After the fix, the async generate() is awaited
    and the deterministic template produces executable Python.
    """
    client, idea_id = app_env
    resp = client.post(f"/ideas/{idea_id}/run-experiment")
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["success"] is True, f"Experiment failed: {body.get('stderr', '')}"
    assert body["exit_code"] == 0
    assert body["idea_id"] == idea_id
    # The deterministic template prints JSON results to stdout
    assert "accuracy" in body["stdout"] or "improvement" in body["stdout"].lower()
    assert body["id"] is not None  # persisted to DB
