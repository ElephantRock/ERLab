"""EAD-4B: Frozen Case 1 production rerun with autonomous experiment design.

Input: domain + research question only.
Autonomous experiment design enabled. No experiment_spec_id.
No seed papers, no hand-selected datasets/citations/method/hypothesis.
"""
import os
import asyncio
import time
from datetime import datetime

os.environ["EROCK_EMBEDDING_MODEL"] = "text-embedding-qwen3-embedding-0.6b"
os.environ["EROCK_EMBEDDING_DIMENSION"] = "1024"
os.environ["EROCK_EMBEDDING_PROVIDER"] = "lmstudio"

import sys
sys.path.insert(0, ".")

from backend.config import get_settings
_settings = get_settings()
print(f"[EAD-4B] model: {_settings.openai_model}", flush=True)
print(f"[EAD-4B] embedding: {_settings.embedding_model}", flush=True)
print(f"[EAD-4B] HEAD: 66382ba", flush=True)
print(
    f"[EAD-4B] autonomous_experiment_enabled: True", flush=True
)
print(
    f"[EAD-4B] experiment_spec_id: NONE"
    f" (autonomous design)", flush=True
)

from backend.pipeline.orchestrator._orchestrator import (
    PipelineOrchestrator,
)


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"[EAD-4B] launch: {ts}", flush=True)

    orchestrator = PipelineOrchestrator(strategy="deep_research")
    start = time.time()
    result = await orchestrator.run(
        domain=(
            "Robust and reliable machine learning"
            " under distribution shift"
        ),
        research_question=(
            "How does post-hoc probability calibration"
            " affect selective classification performance"
            " under covariate shift in tabular"
            " classification, and are the effects"
            " consistent across datasets and shift"
            " severities?"
        ),
        max_gaps=3,
        generation_rounds=1,
        ideas_per_round=1,
        autonomous_experiment_enabled=True,
    )
    elapsed = time.time() - start

    print(f"\n[EAD-4B] COMPLETED in {elapsed:.0f}s", flush=True)
    print(f"[EAD-4B] run_id: {result.run_id}", flush=True)
    print(
        f"[EAD-4B] outcome: {result.outcome}", flush=True
    )
    if result.terminal_stage:
        print(
            f"[EAD-4B] terminal_stage:"
            f" {result.terminal_stage}", flush=True
        )
        print(
            f"[EAD-4B] terminal_reason:"
            f" {result.terminal_reason}", flush=True
        )

    report = getattr(result, "stage_report", None) or []
    skipped_error = 0
    skipped_strategy = 0
    executed = 0
    for s in report:
        if isinstance(s, dict):
            status = s.get("status", "")
        else:
            status = getattr(s, "status", "")
        if status == "executed":
            executed += 1
        elif status == "skipped_by_error":
            skipped_error += 1
        elif status == "skipped_by_strategy":
            skipped_strategy += 1

    print(f"[EAD-4B] executed: {executed}", flush=True)
    print(
        f"[EAD-4B] skipped_by_error:"
        f" {skipped_error}", flush=True
    )
    print(
        f"[EAD-4B] skipped_by_strategy:"
        f" {skipped_strategy}", flush=True
    )

    auto = result.params_used.get(
        "autonomous_experiment_design"
    )
    if auto:
        print(
            f"[EAD-4B] auto_design_status:"
            f" {auto.get('status')}", flush=True
        )
        if auto.get("specs"):
            for spec in auto["specs"]:
                ds = spec.get("dataset", {}).get("name", "?")
                print(f"[EAD-4B] spec: {ds}", flush=True)

    print(
        f"\n[EAD-4B] run_id_str for DB:"
        f" {result.run_id}", flush=True
    )


if __name__ == "__main__":
    asyncio.run(main())
