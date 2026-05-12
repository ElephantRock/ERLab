"""Evaluation API routes — benchmark generation and retrieval evaluation.

BATCH-RAG-01/TASK-04: API endpoints for:
- Generating benchmark datasets from completed pipeline runs
- Listing available benchmarks
- Running retrieval benchmarks against search
- Getting benchmark results
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.pipeline.evaluation.benchmark_models import (
    BenchmarkDataset,
    BenchmarkRunReport,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluation", tags=["evaluation"])

# In-memory benchmark storage (replaced by DB in RAG-04)
_benchmarks: dict[str, BenchmarkDataset] = {}
_benchmark_reports: list[BenchmarkRunReport] = []


@router.get("/benchmarks", summary="List benchmark datasets")
async def list_benchmarks() -> dict[str, Any]:
    """List all generated benchmark datasets."""
    return {
        "total": len(_benchmarks),
        "benchmarks": [
            {
                "id": b.id,
                "name": b.name,
                "domain": b.domain,
                "questions": b.total_questions,
                "papers": b.papers_count,
                "created_at": b.created_at.isoformat(),
            }
            for b in _benchmarks.values()
        ],
    }


@router.get("/benchmarks/{benchmark_id}", summary="Get benchmark dataset")
async def get_benchmark(benchmark_id: str) -> dict[str, Any]:
    """Get a specific benchmark dataset by ID."""
    if benchmark_id not in _benchmarks:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return _benchmarks[benchmark_id].to_dict()


@router.post(
    "/benchmarks/generate",
    summary="Generate benchmark from pipeline run",
)
async def generate_benchmark(
    run_id: str | None = None,
    domain: str = "",
    questions_per_paper: int = 3,
) -> dict[str, Any]:
    """Generate a benchmark dataset from a completed pipeline run's papers.

    Uses the papers found during a pipeline run to create ground-truth
    questions for retrieval evaluation.
    """
    try:
        from backend.config import get_settings
        from backend.db.database import get_session
        from backend.pipeline.evaluation.benchmark_generator import BenchmarkGenerator
        from backend.pipeline.literature.models import Paper
        from backend.providers.provider_factory import create_provider

        settings = get_settings()

        # Get papers from DB
        with get_session() as session:
            from backend.db.models import Paper as DBPaper

            query = session.query(DBPaper)
            if domain:
                query = query.filter(DBPaper.domain.ilike(f"%{domain}%"))
            db_papers = query.limit(50).all()

            if not db_papers:
                raise HTTPException(
                    status_code=404,
                    detail="No papers found for benchmark generation",
                )

            papers = []
            for dbp in db_papers:
                papers.append(
                    Paper(
                        id=str(dbp.id),
                        source=dbp.source or "unknown",
                        title=dbp.title,
                        abstract=dbp.abstract,
                        year=dbp.year,
                    )
                )

        # Create generator with local LLM
        try:
            provider = create_provider("lmstudio")
        except Exception:
            provider = None

        generator = BenchmarkGenerator(
            provider=provider,
            questions_per_paper=min(5, max(1, questions_per_paper)),
        )

        dataset = await generator.generate(
            papers=papers,
            domain=domain,
            source_run_id=run_id,
        )

        # Store in memory
        _benchmarks[dataset.id] = dataset

        return {
            "status": "generated",
            "benchmark_id": dataset.id,
            "questions": dataset.total_questions,
            "papers": dataset.papers_count,
            "domain": dataset.domain,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Benchmark generation failed: %s", str(e)[:200])
        raise HTTPException(
            status_code=500, detail=f"Benchmark generation failed: {str(e)[:100]}"
        )


@router.post(
    "/benchmarks/{benchmark_id}/run",
    summary="Run retrieval benchmark",
)
async def run_benchmark(
    benchmark_id: str,
    strategy: str = "default",
    top_k: int = 10,
) -> dict[str, Any]:
    """Run a retrieval benchmark: search for each question, measure quality."""
    if benchmark_id not in _benchmarks:
        raise HTTPException(status_code=404, detail="Benchmark not found")

    dataset = _benchmarks[benchmark_id]

    try:
        from backend.config import get_settings
        from backend.pipeline.evaluation.retrieval_benchmark import (
            RetrievalBenchmarkRunner,
        )
        from backend.pipeline.literature.search_service import SearchService

        search_service = SearchService()
        runner = RetrievalBenchmarkRunner(search_service=search_service, top_k=top_k)

        report = await runner.run(dataset=dataset, strategy=strategy)
        _benchmark_reports.append(report)

        return {
            "status": "completed",
            "dataset_id": report.dataset_id,
            "total_questions": report.total_questions,
            "questions_found": report.questions_found,
            "hit_rate": round(report.hit_rate, 4),
            "mrr": round(report.mrr, 4),
            "ndcg_at_k": round(report.ndcg_at_k, 4),
            "k": report.k,
            "elapsed_seconds": round(report.elapsed_seconds, 1),
        }

    except Exception as e:
        logger.error("Benchmark run failed: %s", str(e)[:200])
        raise HTTPException(
            status_code=500, detail=f"Benchmark run failed: {str(e)[:100]}"
        )


@router.get("/reports", summary="List benchmark run reports")
async def list_reports() -> dict[str, Any]:
    """List all benchmark run reports."""
    return {
        "total": len(_benchmark_reports),
        "reports": [
            {
                "dataset_id": r.dataset_id,
                "strategy": r.strategy,
                "hit_rate": round(r.hit_rate, 4),
                "mrr": round(r.mrr, 4),
                "ndcg_at_k": round(r.ndcg_at_k, 4),
                "total_questions": r.total_questions,
                "elapsed_seconds": round(r.elapsed_seconds, 1),
            }
            for r in _benchmark_reports
        ],
    }


@router.get("/pipeline-metrics/{run_id}", summary="Get retrieval metrics for a pipeline run")
async def get_pipeline_metrics(run_id: int) -> dict[str, Any]:
    """Get retrieval metrics computed during a pipeline run.

    Returns metrics from the pipeline_metrics DB table.
    """
    try:
        from backend.pipeline.evaluation.metrics_persistence import get_metrics_for_run
        from backend.db.database import get_session
        from backend.db.models import PipelineRun

        with get_session() as session:
            run = session.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if not run:
                raise HTTPException(status_code=404, detail="Pipeline run not found")

        metrics_by_stage = get_metrics_for_run(run_id)

        return {
            "run_id": run_id,
            "domain": run.domain,
            "status": run.status,
            "metrics": metrics_by_stage,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get pipeline metrics: %s", str(e)[:200])
        raise HTTPException(
            status_code=500, detail=f"Failed to get metrics: {str(e)[:100]}"
        )


@router.get("/metrics/history/{metric_name}", summary="Get metric history")
async def get_metric_history_api(metric_name: str, limit: int = 50) -> dict[str, Any]:
    """Get historical values for a specific metric across all runs."""
    try:
        from backend.pipeline.evaluation.metrics_persistence import get_metric_history
        history = get_metric_history(metric_name, limit=limit)
        return {
            "metric": metric_name,
            "count": len(history),
            "history": history,
        }
    except Exception as e:
        logger.error("Failed to get metric history: %s", str(e)[:200])
        raise HTTPException(
            status_code=500, detail=f"Failed to get history: {str(e)[:100]}"
        )
