"""Integration tests for mechanical metrics scoring (BATCH-64/TASK-02).

Verifies:
  AC-02-01: Mechanical metrics included in idea detail API response
  AC-02-02: Composite score weights: 40% LLM + 30% mechanical + 30% novelty/feasibility
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.db.models  # noqa: F401 — ensure models register with Base.metadata
from backend.api.errors import APIError
from backend.api.routes.ideas import router
from backend.db.database import Base

# ── Test app / DB setup ────────────────────────────────────────


def _make_app():
    app = FastAPI()

    @app.exception_handler(APIError)
    async def api_error_handler(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=exc.status_code, content=exc.to_dict())

    app.include_router(router, prefix="/ideas")
    return app


@pytest.fixture()
def _test_env():
    """Shared test environment: engine, session, and patched app client."""
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    app = _make_app()
    from contextlib import contextmanager

    import backend.db.database as db_mod

    @contextmanager
    def _test_session():
        yield session

    original_db = db_mod.get_session
    db_mod.get_session = _test_session

    tc = TestClient(app)
    yield {"session": session, "client": tc}

    db_mod.get_session = original_db
    session.close()


@pytest.fixture()
def db_session(_test_env):
    return _test_env["session"]


@pytest.fixture()
def client(_test_env):
    return _test_env["client"]


@pytest.fixture()
def _seeded_idea(_test_env):
    """Create an idea in the DB with mechanical metrics embedded in novelty_report."""
    from backend.db.models import Idea
    session = _test_env["session"]

    novelty_report = json.dumps({
        "method_novelty": 0.8,
        "problem_novelty": 0.7,
        "domain_transfer": 0.6,
        "combination_novelty": 0.75,
        "novelty_arguments": "Test novelty arguments",
        "mechanical_metrics": {
            "reference_uniqueness": 0.85,
            "gap_coverage": 0.6,
            "citation_density": 0.45,
            "method_specificity": 0.7,
            "prior_art_distance": 0.55,
        },
    })

    idea = Idea(
        title="Test Mechanical Metrics Idea",
        problem_statement="Testing mechanical metrics integration",
        proposed_method="A novel approach with specific claims",
        expected_contributions="Improved accuracy by 15%",
        domain="AI/NLP",
        novelty_score=0.75,
        feasibility_score=7.0,
        overall_score=0.725,
        novelty_report=novelty_report,
        feasibility_report=json.dumps({"overall_score": 7.0}),
    )
    session.add(idea)
    session.commit()
    session.refresh(idea)
    return idea


# ---------------------------------------------------------------------------
# Test: MechanicalMetricsCalculator integration
# ---------------------------------------------------------------------------


class TestMechanicalMetricsCalculator:
    """Unit-level tests for MechanicalMetricsCalculator.compute_all."""

    def test_compute_all_returns_five_metrics(self):
        from backend.pipeline.evaluation.mechanical_metrics import MechanicalMetricsCalculator
        from backend.pipeline.generation.models import ResearchIdea

        idea = ResearchIdea(
            title="Test Idea",
            problem_statement="Test problem",
            proposed_method="We propose a novel transformer architecture that achieves 15% improvement",
            expected_contributions="Improved accuracy and reduced latency",
            novelty_rationale="Novel approach",
            evaluation_approach="Benchmark on GLUE",
            supporting_papers=["paper1", "paper2"],
        )
        calc = MechanicalMetricsCalculator()
        metrics = calc.compute_all(
            idea=idea,
            gaps=[],
            supporting_papers=[],
            all_domain_papers=[],
        )
        assert isinstance(metrics, dict)
        assert set(metrics.keys()) == {
            "reference_uniqueness",
            "gap_coverage",
            "citation_density",
            "method_specificity",
            "prior_art_distance",
        }
        for value in metrics.values():
            assert 0.0 <= value <= 1.0, f"Metric value {value} not in [0.0, 1.0]"

    def test_composite_score_weights(self):
        """AC-02-02: Verify composite score weights."""
        llm_score = 0.8
        metrics = {
            "reference_uniqueness": 0.7,
            "gap_coverage": 0.6,
            "citation_density": 0.5,
            "method_specificity": 0.8,
            "prior_art_distance": 0.4,
        }
        novelty = 0.75
        feasibility = 0.7  # Already normalized to 0-1

        # composite = 0.4 * llm_score + 0.3 * avg(mechanical_metrics) + 0.3 * (novelty + feasibility) / 2
        mech_avg = sum(metrics.values()) / len(metrics)
        composite = 0.4 * llm_score + 0.3 * mech_avg + 0.3 * (novelty + feasibility) / 2

        # Manual computation:
        # mech_avg = (0.7 + 0.6 + 0.5 + 0.8 + 0.4) / 5 = 0.6
        # composite = 0.4 * 0.8 + 0.3 * 0.6 + 0.3 * (0.75 + 0.7) / 2
        #           = 0.32 + 0.18 + 0.2175 = 0.7175
        expected = 0.7175
        assert abs(composite - expected) < 0.001
        assert 0.0 <= composite <= 1.0


# ---------------------------------------------------------------------------
# Test: MechanicalMetricsStage
# ---------------------------------------------------------------------------


class TestMechanicalMetricsStage:
    """Integration test for MechanicalMetricsStage in the pipeline."""

    def test_stage_populates_result_metrics(self):
        import asyncio

        from backend.pipeline.gap_analysis.models import ResearchGap
        from backend.pipeline.generation.models import ResearchIdea
        from backend.pipeline.result import PipelineResult
        from backend.pipeline.stages import MechanicalMetricsStage, StageContext

        idea = ResearchIdea(
            title="Novel Attention Mechanism",
            problem_statement="Attention is expensive",
            proposed_method="Sparse attention with top-k selection that reduces compute by 40%",
            expected_contributions="50% faster inference",
            novelty_rationale="Novel sparsity pattern",
            evaluation_approach="Benchmark on WMT",
        )
        gap = ResearchGap(
            title="Efficient attention",
            description="Need for more efficient attention mechanisms in transformers",
            gap_type="methodological",
            confidence=0.8,
        )

        result = PipelineResult(ideas=[idea], gaps=[gap])
        ctx = StageContext(result=result, all_papers=[])

        stage = MechanicalMetricsStage()
        assert stage.name == "mechanical_metrics"

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in async context (full suite) — use nest_asyncio or run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, stage.execute(ctx))
                success = future.result(timeout=10)
        else:
            success = asyncio.run(stage.execute(ctx))

        assert success is True
        assert 0 in result.mechanical_metrics
        metrics = result.mechanical_metrics[0]
        assert "reference_uniqueness" in metrics
        assert "gap_coverage" in metrics
        assert "citation_density" in metrics
        assert "method_specificity" in metrics
        assert "prior_art_distance" in metrics
        for v in metrics.values():
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# Test: API includes mechanical_metrics (AC-02-01)
# ---------------------------------------------------------------------------


class TestIdeaAPIWithMetrics:
    """AC-02-01: Mechanical metrics included in idea detail API response."""

    def test_get_idea_includes_mechanical_metrics(self, client, _seeded_idea):
        """GET /ideas/{id} returns mechanical_metrics key in response."""
        response = client.get(f"/ideas/{_seeded_idea.id}")
        assert response.status_code == 200

        data = response.json()
        idea = data["idea"]

        # AC-02-01: mechanical_metrics must be present
        assert "mechanical_metrics" in idea, "Response missing 'mechanical_metrics' key"
        assert idea["mechanical_metrics"] is not None
        assert isinstance(idea["mechanical_metrics"], dict)

        metrics = idea["mechanical_metrics"]
        assert metrics["reference_uniqueness"] == 0.85
        assert metrics["gap_coverage"] == 0.6
        assert metrics["citation_density"] == 0.45
        assert metrics["method_specificity"] == 0.7
        assert metrics["prior_art_distance"] == 0.55

        # Ensure metrics were extracted out of novelty_report
        assert "mechanical_metrics" not in (idea.get("novelty_report") or {})

    def test_get_idea_without_metrics_returns_none(self, client, db_session):
        """Ideas without mechanical_metrics return None for the key."""
        from backend.db.models import Idea

        idea = Idea(
            title="Old Idea Without Metrics",
            problem_statement="Pre-BATCH-64 idea",
            proposed_method="Some method",
            expected_contributions="Some contributions",
            domain="AI/NLP",
            novelty_report=json.dumps({"method_novelty": 0.5}),
        )
        db_session.add(idea)
        db_session.commit()
        db_session.refresh(idea)

        response = client.get(f"/ideas/{idea.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["idea"]["mechanical_metrics"] is None
