#!/usr/bin/env python3
"""Live pipeline progress monitor using SSE.

Usage:
    python scripts/monitor.py [--run-id RUN_ID]

If --run-id is omitted, watches for the latest running pipeline.
"""

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000/api/v1"


def get_latest_running_run():
    """Find the most recent running pipeline run."""
    url = f"{BASE_URL}/pipeline/runs"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())
    runs = data.get("runs", [])
    for r in runs:
        if r.get("status") == "running":
            return r
    # Return latest if none running
    return runs[0] if runs else None


def get_run_detail(run_id_int):
    """Get run details by integer ID."""
    url = f"{BASE_URL}/pipeline/runs/detail/{run_id_int}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m {s}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m {s}s"


STAGE_ORDER = [
    "literature_search", "ingestion", "gap_analysis",
    "idea_generation", "novelty_checking", "feasibility_scoring",
    "mechanical_metrics", "proposal_synthesis", "proposal_deepening",
    "export",
]

STAGE_ICONS = {
    "literature_search": "🔍",
    "ingestion": "📥",
    "gap_analysis": "🕳️",
    "idea_generation": "💡",
    "novelty_checking": "✨",
    "feasibility_scoring": "📊",
    "mechanical_metrics": "⚙️",
    "proposal_synthesis": "📝",
    "proposal_deepening": "🔬",
    "export": "📦",
    "completed": "✅",
    "failed": "❌",
}


def monitor_run(run_id_str):
    """Poll-based monitor — checks status every 3 seconds."""
    print(f"╔══════════════════════════════════════════════════════════╗")
    print(f"║  Pipeline Monitor: {run_id_str:<38s}║")
    print(f"╚══════════════════════════════════════════════════════════╝")
    print()

    # Find the integer run ID
    url = f"{BASE_URL}/pipeline/runs"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())

    run = None
    for r in data.get("runs", []):
        # Match by run_id string or by being the latest
        if r.get("status") == "running" or run is None:
            run = r
            if r.get("status") == "running":
                break

    if not run:
        print("No runs found.")
        return

    run_id_int = run["id"]
    start_time = None
    prev_stage = None
    stage_durations = {}
    last_lm_studio = 0
    last_zai = 0

    try:
        while True:
            try:
                url = f"{BASE_URL}/pipeline/runs"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())

                run = None
                for r in data.get("runs", []):
                    if r["id"] == run_id_int:
                        run = r
                        break

                if not run:
                    print("Run not found.")
                    break

                status = run.get("status", "?")
                stage = run.get("current_stage", "?")
                ideas = run.get("ideas_count", 0)
                created = run.get("created_at", "")
                error = run.get("error_message", "")

                if start_time is None and created:
                    try:
                        start_time = datetime.fromisoformat(created)
                    except:
                        start_time = datetime.now()

                elapsed = (datetime.now() - start_time).total_seconds() if start_time else 0

                # Detect stage transitions
                if stage != prev_stage and prev_stage is not None:
                    icon_new = STAGE_ICONS.get(stage, "⏳")
                    icon_old = STAGE_ICONS.get(prev_stage, "⏳")
                    ts = datetime.now().strftime("%H:%M:%S")
                    print(f"  {ts}  {icon_old} {prev_stage} → {icon_new} {stage}  ({format_duration(elapsed)} elapsed)")

                    # Print a summary line
                    if status == "completed":
                        print(f"\n  ✅ COMPLETED — {ideas} ideas in {format_duration(elapsed)}")
                    elif status == "failed":
                        print(f"\n  ❌ FAILED — {error}")

                prev_stage = stage

                if status in ("completed", "failed"):
                    # Final summary
                    completed_at = run.get("completed_at", "")
                    print(f"\n  Run #{run_id_int}: {status}")
                    print(f"  Ideas: {ideas}")
                    print(f"  Started: {created}")
                    print(f"  Finished: {completed_at}")
                    if error:
                        print(f"  Error: {error}")
                    break

            except Exception as e:
                ts = datetime.now().strftime("%H:%M:%S")
                print(f"  {ts}  ⚠️ Poll error: {e}")

            time.sleep(3)

    except KeyboardInterrupt:
        print("\n  Monitor stopped.")


def main():
    parser = argparse.ArgumentParser(description="Pipeline progress monitor")
    parser.add_argument("--run-id", help="Run ID string (e.g. run_20260509_155035)")
    args = parser.parse_args()

    run_id = args.run_id
    if not run_id:
        run = get_latest_running_run()
        if run:
            print(f"Auto-detected running pipeline: Run #{run['id']}")
            # We need the string run_id for the API
            # Use the integer ID approach instead
        else:
            print("No running pipelines found. Use --run-id to specify.")
            sys.exit(1)

    monitor_run(run_id or "latest")


if __name__ == "__main__":
    main()
