"""Eval Sidecar — reads stage logs + benchmark, computes metrics, writes SQLite.

BATCH-182 / TASK-02: Post-hoc evaluation of pipeline runs. Reads the structured
JSON logs written by StageLogger during pipeline execution, cross-references with
benchmark data from the dataset generator, and computes quality/performance metrics.

Usage:
    python -m backend.pipeline.dag.eval_sidecar --run-id run_20260513_080000
    python -m backend.pipeline.dag.eval_sidecar --all
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_LOG_DIR = "logs/pipeline"
_DEFAULT_DB = "data/elephant_rock.db"
_METRICS_TABLE = "dag_evaluation_metrics"


def evaluate_run(
    run_id: str,
    logs_dir: str = _DEFAULT_LOG_DIR,
    benchmark_path: str | None = None,
    db_path: str = _DEFAULT_DB,
) -> dict[str, Any]:
    """Post-hoc evaluation of a single pipeline run.

    Reads stage logs, computes metrics, writes to SQLite.

    Args:
        run_id: The pipeline run ID (e.g., "run_20260513_080000").
        logs_dir: Directory containing stage log JSONL files.
        benchmark_path: Optional path to benchmark JSON for comparison.
        db_path: Path to SQLite database for persisting metrics.

    Returns:
        Dict of computed metrics.
    """
    logs = _load_stage_logs(logs_dir, run_id)
    if not logs:
        logger.warning("No stage logs found for run %s", run_id)
        return {"run_id": run_id, "error": "no_logs_found"}

    # Load benchmark for comparison (optional)
    benchmark = None
    if benchmark_path and Path(benchmark_path).exists():
        benchmark = _load_benchmark(benchmark_path)

    metrics = _compute_metrics(run_id, logs, benchmark)

    # Persist to SQLite
    _persist_metrics(metrics, db_path)

    logger.info("Eval sidecar: %d metrics computed for run %s", len(metrics), run_id)
    return metrics


def evaluate_all(
    logs_dir: str = _DEFAULT_LOG_DIR,
    benchmark_path: str | None = None,
    db_path: str = _DEFAULT_DB,
) -> list[dict[str, Any]]:
    """Evaluate all runs that have stage logs.

    Returns:
        List of metric dicts, one per run.
    """
    logs_path = Path(logs_dir)
    if not logs_path.exists():
        logger.warning("Logs directory not found: %s", logs_dir)
        return []

    # Find all unique run_ids from log filenames
    run_ids = set()
    for log_file in logs_path.glob("*.jsonl"):
        # Filename format: {run_id}.jsonl
        run_id = log_file.stem
        run_ids.add(run_id)

    results = []
    for run_id in sorted(run_ids):
        metrics = evaluate_run(run_id, logs_dir, benchmark_path, db_path)
        results.append(metrics)

    logger.info("Eval sidecar: evaluated %d runs", len(results))
    return results


def _load_stage_logs(logs_dir: str, run_id: str) -> list[dict]:
    """Load stage log entries for a specific run."""
    log_file = Path(logs_dir) / f"{run_id}.jsonl"
    if not log_file.exists():
        return []

    entries = []
    with open(log_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Corrupt log line in %s: %s", log_file, line[:80])
    return entries


def _load_benchmark(benchmark_path: str) -> dict | None:
    """Load benchmark JSON file."""
    try:
        with open(benchmark_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.warning("Could not load benchmark: %s", e)
        return None


def _compute_metrics(
    run_id: str, logs: list[dict], benchmark: dict | None
) -> dict[str, Any]:
    """Compute evaluation metrics from stage logs."""
    # Total elapsed time
    total_elapsed = sum(l.get("elapsed_s", 0) for l in logs)

    # Stage counts
    stage_count = len(logs)
    stages_with_error = [l["stage"] for l in logs if l.get("error")]
    stages_completed = [l["stage"] for l in logs if l.get("event") == "complete"]

    # Input/output counts
    total_papers_in = sum(l.get("inputs", {}).get("papers", 0) for l in logs)
    total_gaps_out = sum(l.get("outputs", {}).get("gaps", 0) for l in logs)
    total_ideas_out = sum(l.get("outputs", {}).get("ideas", 0) for l in logs)
    total_proposals_out = sum(l.get("outputs", {}).get("proposals", 0) for l in logs)

    # Ratios
    papers_to_ideas = (
        total_ideas_out / total_papers_in if total_papers_in > 0 else 0.0
    )
    gaps_to_proposals = (
        total_proposals_out / total_gaps_out if total_gaps_out > 0 else 0.0
    )

    # Average elapsed per stage
    avg_stage_elapsed = total_elapsed / stage_count if stage_count > 0 else 0.0

    # Slowest stage
    slowest = max(logs, key=lambda l: l.get("elapsed_s", 0)) if logs else {}
    slowest_stage = slowest.get("stage", "unknown")
    slowest_elapsed = slowest.get("elapsed_s", 0)

    # Model categories used
    categories = set()
    for l in logs:
        cat = l.get("config", {}).get("model_category", "unknown")
        if cat != "unknown":
            categories.add(cat)

    # Reranker detection
    reranker_used = any(l.get("stage") == "trimmer" for l in logs)

    # Citation fabrication proxy: stages with errors mentioning "citation" or "fabrication"
    citation_issues = sum(
        1
        for l in logs
        if l.get("error") and ("citation" in str(l["error"]).lower() or "fabricat" in str(l["error"]).lower())
    )

    # Benchmark comparison (if available)
    benchmark_entry = None
    if benchmark and "runs" in benchmark:
        # Find this run in benchmark by looking at recent runs
        benchmark_entry = {
            "total_benchmark_runs": benchmark.get("run_count", 0),
            "avg_benchmark_elapsed": _avg_benchmark_elapsed(benchmark),
        }

    metrics = {
        "run_id": run_id,
        "evaluated_at": datetime.now(UTC).isoformat(),
        # Timing
        "total_elapsed_s": round(total_elapsed, 2),
        "avg_stage_elapsed_s": round(avg_stage_elapsed, 2),
        "slowest_stage": slowest_stage,
        "slowest_stage_elapsed_s": round(slowest_elapsed, 2),
        # Counts
        "stage_count": stage_count,
        "stages_completed": stages_completed,
        "stages_with_error": stages_with_error,
        # Pipeline metrics
        "total_papers_in": total_papers_in,
        "total_gaps_out": total_gaps_out,
        "total_ideas_out": total_ideas_out,
        "total_proposals_out": total_proposals_out,
        "papers_to_ideas_ratio": round(papers_to_ideas, 3),
        "gaps_to_proposals_ratio": round(gaps_to_proposals, 3),
        # Quality signals
        "reranker_used": reranker_used,
        "citation_issues": citation_issues,
        "model_categories_used": sorted(categories),
        # Benchmark
        "benchmark_comparison": benchmark_entry,
    }
    return metrics


def _avg_benchmark_elapsed(benchmark: dict) -> float:
    """Compute average elapsed time from benchmark runs."""
    elapsed_values = [
        r["elapsed_s"] for r in benchmark.get("runs", []) if r.get("elapsed_s")
    ]
    if not elapsed_values:
        return 0.0
    return round(sum(elapsed_values) / len(elapsed_values), 2)


def _persist_metrics(metrics: dict, db_path: str) -> None:
    """Write metrics to SQLite dag_evaluation_metrics table."""
    db = Path(db_path)
    conn = sqlite3.connect(str(db))

    try:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_METRICS_TABLE} (
                run_id TEXT PRIMARY KEY,
                evaluated_at TEXT,
                total_elapsed_s REAL,
                avg_stage_elapsed_s REAL,
                slowest_stage TEXT,
                slowest_stage_elapsed_s REAL,
                stage_count INTEGER,
                stages_completed TEXT,
                stages_with_error TEXT,
                total_papers_in INTEGER,
                total_gaps_out INTEGER,
                total_ideas_out INTEGER,
                total_proposals_out INTEGER,
                papers_to_ideas_ratio REAL,
                gaps_to_proposals_ratio REAL,
                reranker_used INTEGER,
                citation_issues INTEGER,
                model_categories_used TEXT,
                benchmark_comparison TEXT
            )
            """
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO {_METRICS_TABLE} (
                run_id, evaluated_at, total_elapsed_s, avg_stage_elapsed_s,
                slowest_stage, slowest_stage_elapsed_s, stage_count,
                stages_completed, stages_with_error,
                total_papers_in, total_gaps_out, total_ideas_out, total_proposals_out,
                papers_to_ideas_ratio, gaps_to_proposals_ratio,
                reranker_used, citation_issues,
                model_categories_used, benchmark_comparison
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metrics["run_id"],
                metrics["evaluated_at"],
                metrics["total_elapsed_s"],
                metrics["avg_stage_elapsed_s"],
                metrics["slowest_stage"],
                metrics["slowest_stage_elapsed_s"],
                metrics["stage_count"],
                json.dumps(metrics["stages_completed"]),
                json.dumps(metrics["stages_with_error"]),
                metrics["total_papers_in"],
                metrics["total_gaps_out"],
                metrics["total_ideas_out"],
                metrics["total_proposals_out"],
                metrics["papers_to_ideas_ratio"],
                metrics["gaps_to_proposals_ratio"],
                1 if metrics["reranker_used"] else 0,
                metrics["citation_issues"],
                json.dumps(metrics["model_categories_used"]),
                json.dumps(metrics.get("benchmark_comparison")),
            ),
        )
        conn.commit()
    finally:
        conn.close()


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate pipeline runs from stage logs")
    parser.add_argument("--run-id", help="Evaluate a specific run")
    parser.add_argument("--all", action="store_true", help="Evaluate all runs with logs")
    parser.add_argument("--logs-dir", default=_DEFAULT_LOG_DIR, help="Stage logs directory")
    parser.add_argument("--benchmark", help="Path to benchmark JSON")
    parser.add_argument("--db", default=_DEFAULT_DB, help="SQLite database path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.all:
        results = evaluate_all(args.logs_dir, args.benchmark, args.db)
        for r in results:
            print(f"  {r.get('run_id', '?')}: {r.get('total_elapsed_s', 0):.1f}s, {r.get('stage_count', 0)} stages")
        print(f"Evaluated {len(results)} runs")
    elif args.run_id:
        metrics = evaluate_run(args.run_id, args.logs_dir, args.benchmark, args.db)
        print(json.dumps(metrics, indent=2, default=str))
    else:
        parser.error("Specify --run-id or --all")


if __name__ == "__main__":
    main()
