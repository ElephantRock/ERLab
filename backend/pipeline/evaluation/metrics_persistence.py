"""Metrics persistence service — stores evaluation metrics in DB.

BATCH-RAG-04/TASK-02: Provides a simple interface to persist evaluation
metrics from any pipeline stage. Metrics are stored as (run_id, stage,
metric_name, metric_value) tuples.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)


def persist_metrics(
    run_id: int,
    stage: str,
    metrics: dict[str, float],
    detail: str | dict | None = None,
) -> bool:
    """Persist evaluation metrics for a pipeline run.

    Parameters
    ----------
    run_id:
        Database ID of the pipeline run.
    stage:
        Stage name (e.g., "literature_search", "proposal_synthesis").
    metrics:
        Dict of metric_name → metric_value pairs.
    detail:
        Optional detail string or dict for additional context.

    Returns True if successful.
    """
    try:
        from backend.db.database import get_session
        from backend.db.metrics_models import PipelineMetric

        detail_str = None
        if detail is not None:
            detail_str = (
                json.dumps(detail) if isinstance(detail, dict) else str(detail)
            )

        with get_session() as session:
            for name, value in metrics.items():
                metric = PipelineMetric(
                    run_id=run_id,
                    stage=stage,
                    metric_name=name,
                    metric_value=float(value),
                    detail=detail_str,
                )
                session.add(metric)
            session.commit()

        logger.info(
            "Persisted %d metrics for run %d stage %s",
            len(metrics),
            run_id,
            stage,
        )
        return True

    except Exception as e:
        logger.warning("Failed to persist metrics: %s", str(e)[:100])
        return False


def get_metrics_for_run(run_id: int) -> dict[str, list[dict]]:
    """Get all metrics for a pipeline run, grouped by stage.

    Returns: {"stage_name": [{"name": ..., "value": ...}, ...]}
    """
    try:
        from backend.db.database import get_session
        from backend.db.metrics_models import PipelineMetric

        with get_session() as session:
            metrics = (
                session.query(PipelineMetric)
                .filter(PipelineMetric.run_id == run_id)
                .order_by(PipelineMetric.stage, PipelineMetric.metric_name)
                .all()
            )

            result: dict[str, list[dict]] = {}
            for m in metrics:
                if m.stage not in result:
                    result[m.stage] = []
                result[m.stage].append({
                    "name": m.metric_name,
                    "value": m.metric_value,
                    "detail": m.detail,
                })
            return result

    except Exception as e:
        logger.warning("Failed to get metrics: %s", str(e)[:100])
        return {}


def get_metric_history(
    metric_name: str,
    limit: int = 50,
) -> list[dict]:
    """Get historical values for a specific metric across all runs.

    Useful for tracking metric trends (e.g., hit_rate over time).
    """
    try:
        from backend.db.database import get_session
        from backend.db.metrics_models import PipelineMetric

        with get_session() as session:
            metrics = (
                session.query(PipelineMetric)
                .filter(PipelineMetric.metric_name == metric_name)
                .order_by(PipelineMetric.created_at.desc())
                .limit(limit)
                .all()
            )

            return [
                {
                    "run_id": m.run_id,
                    "stage": m.stage,
                    "value": m.metric_value,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in metrics
            ]

    except Exception as e:
        logger.warning("Failed to get metric history: %s", str(e)[:100])
        return []
