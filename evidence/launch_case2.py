"""Case 2: Repeatability qualification — frozen production launch.

Input: domain + research question only (Case 2 charter).
Autonomous experiment design enabled. No experiment_spec_id.
No dataset names, no expected metrics, no expected conclusions.

Frozen head: 1cb8fe048300b5813395eb637feb38b77f52ff8a (main).
Manifest pre-registered and hashed before this launch:
evidence/case2_manifest.json (sha256 in evidence/case2_manifest.sha256).
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
print(f"[CASE2] model: {_settings.openai_model}", flush=True)
print(f"[CASE2] HEAD: 1cb8fe0", flush=True)
print(f"[CASE2] manifest sha256: 4a161e0aa53902b165d811ef122acd8e796678e0c888edcc1293473e5cdc7eea", flush=True)
print(f"[CASE2] autonomous_experiment_enabled: True", flush=True)
print(f"[CASE2] experiment_spec_id: NONE (autonomous design)", flush=True)

from backend.pipeline.orchestrator._orchestrator import (
    PipelineOrchestrator,
)


async def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"[CASE2] launch: {ts}", flush=True)

    orchestrator = PipelineOrchestrator(strategy="deep_research")
    start = time.time()
    result = await orchestrator.run(
        domain=(
            "Robust confidence estimation under dataset shift"
        ),
        research_question=(
            "Are calibration-method rankings stable as"
            " covariate-shift severity increases, or do rank"
            " reversals occur in accuracy, positive-class"
            " expected calibration error, and selective AURC"
            " across tabular classification datasets?"
        ),
        max_gaps=3,
        generation_rounds=1,
        ideas_per_round=1,
        autonomous_experiment_enabled=True,
    )
    elapsed = time.time() - start

    print(f"\n[CASE2] COMPLETED in {elapsed:.0f}s", flush=True)
    print(f"[CASE2] run_id: {result.run_id}", flush=True)
    print(f"[CASE2] outcome: {result.outcome}", flush=True)
    if result.terminal_stage:
        print(f"[CASE2] terminal_stage: {result.terminal_stage}", flush=True)
        print(f"[CASE2] terminal_reason: {result.terminal_reason}", flush=True)

    report = getattr(result, "stage_report", None) or []
    executed = skipped_error = skipped_strategy = 0
    for s in report:
        status = s.get("status", "") if isinstance(s, dict) else getattr(s, "status", "")
        if status == "executed":
            executed += 1
        elif status == "skipped_by_error":
            skipped_error += 1
        elif status == "skipped_by_strategy":
            skipped_strategy += 1
    print(f"[CASE2] executed: {executed}", flush=True)
    print(f"[CASE2] skipped_by_error: {skipped_error}", flush=True)
    print(f"[CASE2] skipped_by_strategy: {skipped_strategy}", flush=True)

    auto = result.params_used.get("autonomous_experiment_design")
    if auto:
        print(f"[CASE2] auto_design_status: {auto.get('status')}", flush=True)
        for spec in auto.get("specs", []):
            ds = spec.get("dataset", {}).get("name", "?")
            print(f"[CASE2] spec: {ds}", flush=True)

    print(f"\n[CASE2] run_id_str for DB: {result.run_id}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
