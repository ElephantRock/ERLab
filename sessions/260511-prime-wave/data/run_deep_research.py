import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(r"C:\Next-Era\elephant-rock-platform")
sys.path.insert(0, str(PROJECT))

from backend.pipeline.orchestrator import PipelineOrchestrator

DOMAIN = "Event-sourced and transactionally governed multi-agent LLM systems for security-auditable software engineering workflows"
QUERIES = [
    "ESAA Event Sourcing for Autonomous Agents LLM-Based Software Engineering",
    "ESAA-Security event-sourced verifiable architecture agent-assisted security audits AI-generated code",
    "SagaLLM Context Management Validation Transaction Guarantees Multi-Agent LLM Planning",
    "LLM agent governance event sourcing saga compensation security audit reproducibility",
]
RUN_ID = "run_esaa_sagallm_deep_research_" + datetime.now().strftime("%Y%m%d_%H%M%S")
OUT = Path(r"C:\Next-Era\elephant-rock-platform\sessions\260511-prime-wave\data") / f"{RUN_ID}_summary.json"

stage_events = []

def on_stage(stage_name, idx=None, total=None, elapsed=None):
    event = {"stage": stage_name, "idx": idx, "total": total, "elapsed": elapsed}
    stage_events.append(event)
    print("STAGE", json.dumps(event), flush=True)

async def main():
    summary = {"run_id": RUN_ID, "domain": DOMAIN, "queries": QUERIES, "status": "started", "stage_events": stage_events}
    try:
        orch = PipelineOrchestrator(stage_callback=on_stage, strategy="deep_research")
        built_stages = [s.name for s in orch._stages]
        configured_stages = list(getattr(orch, "_STAGE_ORDER", []))
        summary["built_stages"] = built_stages
        summary["configured_stage_order"] = configured_stages
        print("BUILT_STAGES", json.dumps(built_stages), flush=True)
        print("CONFIGURED_STAGES", json.dumps(configured_stages), flush=True)
        result = await orch.run(
            domain=DOMAIN,
            search_queries=QUERIES,
            max_gaps=5,
            generation_rounds=2,
            ideas_per_round=3,
            run_novelty=True,
            run_feasibility=True,
            run_synthesis=True,
            export_format="markdown",
            run_id=RUN_ID,
            session_id="esaa-sagallm-deep-research",
        )
        summary.update({
            "status": "completed",
            "papers_found": getattr(result, "papers_found", None),
            "gaps_count": len(getattr(result, "gaps", []) or []),
            "ideas_count": len(getattr(result, "ideas", []) or []),
            "proposals_count": len(getattr(result, "proposals", []) or []),
            "novelty_reports_count": len(getattr(result, "novelty_reports", {}) or {}),
            "feasibility_reports_count": len(getattr(result, "feasibility_reports", {}) or {}),
            "export_paths": getattr(result, "export_paths", {}) or {},
            "warnings": getattr(result, "warnings", []) if hasattr(result, "warnings") else None,
            "persistence_warnings": getattr(result, "persistence_warnings", []) if hasattr(result, "persistence_warnings") else None,
            "stage_events": stage_events,
        })
        # lightweight details
        summary["gaps"] = [getattr(g, "description", str(g))[:500] for g in (getattr(result, "gaps", []) or [])]
        summary["ideas"] = [
            {
                "title": getattr(i, "title", ""),
                "score": getattr(i, "score", None),
                "problem_statement": getattr(i, "problem_statement", "")[:500],
                "proposed_method": getattr(i, "proposed_method", "")[:500],
            }
            for i in (getattr(result, "ideas", []) or [])
        ]
    except Exception as e:
        summary.update({"status": "failed", "error_type": type(e).__name__, "error": str(e), "stage_events": stage_events})
        print("ERROR", type(e).__name__, str(e), flush=True)
        raise
    finally:
        OUT.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        print("SUMMARY_PATH", str(OUT), flush=True)

if __name__ == "__main__":
    asyncio.run(main())
