"""Dataset Generator — reads historical runs from SQLite, produces benchmark JSON.

BATCH-182 / TASK-01: Offline benchmark generator. Reads completed pipeline runs
from the Elephant Rock SQLite database and produces a JSON benchmark file that
the eval sidecar can use for cross-run comparison.

Usage:
    python -m backend.pipeline.dag.dataset_generator [--output benchmarks/latest.json]
"""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Default DB path (relative to project root)
_DEFAULT_DB = "data/elephant_rock.db"


def generate_benchmark(
    db_path: str = _DEFAULT_DB,
    output_path: str = "benchmarks/latest.json",
    status_filter: str = "completed",
) -> dict[str, Any]:
    """Generate benchmark dataset from completed pipeline runs.

    Args:
        db_path: Path to the Elephant Rock SQLite database.
        output_path: Path to write the benchmark JSON file.
        status_filter: Only include runs with this status (default: "completed").

    Returns:
        The benchmark dict that was written to disk.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    try:
        runs = _fetch_runs(conn, status_filter)
    finally:
        conn.close()

    dataset = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_db": str(db_path),
        "run_count": len(runs),
        "runs": runs,
    }

    # Write to disk
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    logger.info("Benchmark: %d runs written to %s", len(runs), output)
    return dataset


def _fetch_runs(conn: sqlite3.Connection, status_filter: str) -> list[dict]:
    """Fetch runs from DB with their gaps, ideas, and proposals."""
    rows = conn.execute(
        "SELECT id, status, domain, config_json, current_stage, "
        "       stages_completed, stage_report_json, created_at, completed_at, "
        "       session_id "
        "FROM pipeline_runs "
        f"WHERE status = ? "
        "ORDER BY id DESC",
        (status_filter,),
    ).fetchall()

    runs = []
    for row in rows:
        run_id = row["id"]
        entry = {
            "db_id": run_id,
            "domain": row["domain"],
            "status": row["status"],
            "session_id": row["session_id"],
            "created_at": row["created_at"],
            "completed_at": row["completed_at"],
            "current_stage": row["current_stage"],
            "stages_completed": _safe_json(row["stages_completed"], []),
            "stage_report": _safe_json(row["stage_report_json"], {}),
        }

        # Gaps
        gaps = conn.execute(
            "SELECT title, confidence, gap_type FROM research_gaps WHERE pipeline_run_id = ?",
            (run_id,),
        ).fetchall()
        entry["gaps_count"] = len(gaps)
        entry["gaps"] = [
            {"title": g["title"], "confidence": g["confidence"], "type": g["gap_type"]}
            for g in gaps
        ]

        # Ideas
        ideas = conn.execute(
            "SELECT title, novelty_score, feasibility_score, overall_score "
            "FROM ideas WHERE pipeline_run_id = ?",
            (run_id,),
        ).fetchall()
        entry["ideas_count"] = len(ideas)
        entry["ideas"] = [
            {
                "title": i["title"],
                "novelty": i["novelty_score"],
                "feasibility": i["feasibility_score"],
                "overall": i["overall_score"],
            }
            for i in ideas
        ]

        # Proposals (via ideas)
        proposals = conn.execute(
            "SELECT p.content_md, p.references_json "
            "FROM proposals p "
            "JOIN ideas i ON p.idea_id = i.id "
            "WHERE i.pipeline_run_id = ?",
            (run_id,),
        ).fetchall()
        entry["proposals_count"] = len(proposals)
        entry["proposals_word_counts"] = [
            len((p["content_md"] or "").split()) for p in proposals
        ]

        # Compute elapsed time
        if row["created_at"] and row["completed_at"]:
            try:
                created = _parse_dt(row["created_at"])
                completed = _parse_dt(row["completed_at"])
                entry["elapsed_s"] = (completed - created).total_seconds()
            except (ValueError, TypeError):
                entry["elapsed_s"] = None
        else:
            entry["elapsed_s"] = None

        runs.append(entry)

    return runs


def _safe_json(raw: str | None, default: Any) -> Any:
    """Parse JSON string, return default on failure."""
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return default


def _parse_dt(value: str) -> datetime:
    """Parse a datetime string (ISO or common formats)."""
    if isinstance(value, datetime):
        return value
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {value}")


# ── CLI ──────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate benchmark from historical runs")
    parser.add_argument("--db", default=_DEFAULT_DB, help="Path to SQLite database")
    parser.add_argument("--output", default="benchmarks/latest.json", help="Output JSON path")
    parser.add_argument("--status", default="completed", help="Run status filter")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    dataset = generate_benchmark(args.db, args.output, args.status)
    print(f"Generated benchmark: {dataset['run_count']} runs -> {args.output}")


if __name__ == "__main__":
    main()
