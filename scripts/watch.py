#!/usr/bin/env python3
"""Lightweight pipeline progress monitor. Polls every 2s and prints stage transitions.

Usage:
    python scripts/watch.py                  # Watch latest run
    python scripts/watch.py 96               # Watch specific run ID
"""

import json, sys, time, urllib.request
from datetime import datetime

API = "http://127.0.0.1:8000/api/v1"

ICONS = {
    "literature_search": "[SRCH]", "ingestion": "[INGE]", "gap_analysis": "[GAP ]",
    "idea_generation": "[IDEA]", "novelty_checking": "[NOVL]", "feasibility_scoring": "[FEAS]",
    "mechanical_metrics": "[MTRC]", "proposal_synthesis": "[SYNT]", "proposal_deepening": "[DEEP]",
    "export": "[XPORT]",
}

def fmt(s):
    return f"{s:.0f}s" if s < 60 else f"{int(s)//60}m {int(s)%60}s"

def fetch(path):
    with urllib.request.urlopen(f"{API}{path}", timeout=5) as r:
        return json.loads(r.read())

def watch(run_id_int):
    prev_stage = None
    stage_start = None

    while True:
        try:
            data = fetch(f"/pipeline/runs")
            run = next((r for r in data["runs"] if r["id"] == run_id_int), None)
            if not run:
                print(f"Run #{run_id_int} not found")
                return

            stage = run["current_stage"]
            status = run["status"]
            ideas = run["ideas_count"]
            now = datetime.now()

            if stage != prev_stage:
                if prev_stage:
                    dur = fmt((now - stage_start).total_seconds())
                    print(f"  {now:%H:%M:%S}  {ICONS.get(prev_stage, '[    ]')} {prev_stage} done ({dur})")
                if status == "running":
                    print(f"  {now:%H:%M:%S}  {ICONS.get(stage, '[    ]')} {stage} ...", end="", flush=True)
                    stage_start = now
                elif status == "completed":
                    print(f"\n  {now:%H:%M:%S}  [DONE] completed -- {ideas} ideas")
                    return
                elif status == "failed":
                    print(f"\n  {now:%H:%M:%S}  [FAIL] failed -- {run.get('error_message', '')}")
                    return
                prev_stage = stage
            else:
                # Still on same stage — update spinner
                if status == "running" and stage_start:
                    dur = fmt((now - stage_start).total_seconds())
                    print(f"\r  {now:%H:%M:%S}  {ICONS.get(stage, '[    ]')} {stage} ... {dur}  (ideas: {ideas})", end="", flush=True)

        except Exception as e:
            print(f"\n  WARN: {e}")

        time.sleep(2)

if __name__ == "__main__":
    run_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if run_id is None:
        runs = fetch("/pipeline/runs")["runs"]
        r = next((r for r in runs if r["status"] == "running"), runs[0] if runs else None)
        if not r:
            print("No runs found"); sys.exit(1)
        run_id = r["id"]
        print(f"Watching Run #{run_id}: {r.get('domain', '')}")
    watch(run_id)
