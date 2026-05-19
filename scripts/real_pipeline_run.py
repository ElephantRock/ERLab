"""Real Pipeline Run — Inference Speedup Alternatives (Task #127)

Domain: Inference Speedup Alternatives (For Latency Reduction)
Reference: arXiv 2509.24435v1 — Alternatives To Next Token Prediction

This script runs the full 17-stage ERLab pipeline on the domain
and collects enforcement + quality metrics.

Usage:
    PYTHONPATH=. python scripts/real_pipeline_run.py
"""

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/real_pipeline_run.log"),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("=" * 70)
    logger.info("REAL PIPELINE RUN — Inference Speedup Alternatives")
    logger.info("=" * 70)

    # ── 1. Verify LM Studio is reachable ──────────────────────────
    import httpx

    lmstudio_url = os.getenv("LMSTUDIO_BASE_URL", "http://100.64.0.1:1234")
    try:
        resp = httpx.get(f"{lmstudio_url}/v1/models", timeout=10)
        if resp.status_code != 200:
            logger.error("LM Studio returned status %d — aborting", resp.status_code)
            return
        models = resp.json().get("data", [])
        model_ids = [m.get("id", "") for m in models]
        logger.info("LM Studio models: %s", model_ids)
    except Exception as e:
        logger.error("LM Studio not reachable at %s: %s", lmstudio_url, e)
        logger.error("Start LM Studio and load qwen/qwen3-4b-2507, then re-run.")
        return

    # ── 2. Import and configure pipeline ──────────────────────────
    # Force reload settings (pydantic-settings caches on first load)
    import importlib
    import backend.config
    importlib.reload(backend.config)

    from backend.config import get_settings
    from backend.pipeline.orchestrator import PipelineOrchestrator

    settings = get_settings()

    # Override gateway provider to use LM Studio directly (bypass cached anthropic provider)
    import openai as _openai
    _lmstudio_client = _openai.AsyncOpenAI(
        api_key="lm-studio",
        base_url=settings.lmstudio_base_url + "/v1",
    )
    _lmstudio_model = settings.lmstudio_model

    async def _direct_lmstudio_fn(*, messages, temperature, max_tokens, schema=None, tools=None):
        """Call LM Studio directly via OpenAI SDK."""
        if schema:
            try:
                import json as _json
                resp = await _lmstudio_client.chat.completions.create(
                    model=_lmstudio_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {"name": "structured_output", "schema": schema, "strict": True},
                    },
                )
                text = resp.choices[0].message.content or ""
                return _json.loads(text)
            except Exception:
                pass
        resp = await _lmstudio_client.chat.completions.create(
            model=_lmstudio_model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    logger.info("Settings:")
    logger.info("  provider:       %s", settings.default_provider)
    logger.info("  lmstudio_url:   %s", settings.lmstudio_base_url)
    logger.info("  lmstudio_model: %s", settings.lmstudio_model)
    logger.info("  embedding:      %s/%s", settings.embedding_provider, settings.embedding_model)
    logger.info("  generation:     rounds=%d, ideas_per=%d",
                settings.generation_rounds, settings.ideas_per_round)

    # ── 3. Build orchestrator ─────────────────────────────────────
    t0 = time.time()
    logger.info("Building orchestrator...")
    orchestrator = PipelineOrchestrator(settings=settings)
    logger.info("Orchestrator built in %.1fs", time.time() - t0)

    # Override gateway to use LM Studio directly
    orchestrator._gateway.set_provider_fn(_direct_lmstudio_fn)
    logger.info("Gateway provider overridden → LM Studio direct (%s)", settings.lmstudio_base_url)

    # ── 4. Run pipeline ───────────────────────────────────────────
    domain = "Inference Speedup Alternatives for Latency Reduction"
    search_queries = [
        "alternatives to next token prediction LLM inference speedup",
        "multi-token prediction speculative decoding latency reduction",
        "diffusion language models parallel text generation",
        "plan-then-generate models for efficient LLM inference",
        "latent reasoning continuous generation LLM speedup",
        "state space models Mamba efficient inference",
        "Mercury diffusion model real-time text generation",
        "block diffusion autoregressive hybrid inference",
    ]

    logger.info("Running pipeline on domain: %s", domain)
    logger.info("Search queries: %d", len(search_queries))
    for i, q in enumerate(search_queries):
        logger.info("  Q%d: %s", i+1, q)

    t_start = time.time()

    result = await orchestrator.run(
        domain=domain,
        search_queries=search_queries,
        max_gaps=5,
        generation_rounds=1,
        ideas_per_round=2,
        export_format="markdown",
    )

    elapsed = time.time() - t_start

    # ── 5. Collect results ────────────────────────────────────────
    report = {
        "run_id": result.run_id,
        "domain": domain,
        "elapsed_seconds": round(elapsed, 1),
        "papers_found": result.papers_found,
        "gaps_found": len(result.gaps) if result.gaps else 0,
        "ideas_generated": len(result.ideas) if result.ideas else 0,
        "proposals_generated": len(result.proposals) if result.proposals else 0,
        "stage_report": [
            {
                "name": sr.name,
                "status": sr.status,
                "elapsed_s": sr.elapsed_s,
                "error": sr.error[:200] if sr.error else None,
                "retries": sr.retries_used,
            }
            for sr in result.stage_report
        ],
        "enforcement_summary": {},
        "gaps": [],
        "ideas": [],
    }

    # Gaps
    if result.gaps:
        for gap in result.gaps:
            report["gaps"].append({
                "title": gap.title,
                "gap_type": getattr(gap, "gap_type", ""),
                "confidence": getattr(gap, "confidence", 0),
                "description": gap.description[:300] if hasattr(gap, "description") else "",
            })

    # Ideas
    if result.ideas:
        for idea in result.ideas:
            novelty = result.novelty_reports.get(result.ideas.index(idea))
            feasibility = result.feasibility_reports.get(result.ideas.index(idea))
            report["ideas"].append({
                "title": idea.title,
                "score": getattr(idea, "score", 0),
                "proposed_method": idea.proposed_method[:300] if hasattr(idea, "proposed_method") else "",
                "novelty_score": novelty.overall_score if novelty else None,
                "feasibility_score": feasibility.overall_score if feasibility else None,
            })

    # Enforcement from gateway
    try:
        gateway = orchestrator._gateway
        call_log = gateway.get_call_log()
        enforced = [c for c in call_log if c.get("enforcement_applied")]
        degraded = [c for c in call_log if c.get("degraded")]
        report["enforcement_summary"] = {
            "total_calls": len(call_log),
            "enforced_calls": len(enforced),
            "degraded_calls": len(degraded),
            "stages_seen": list(set(c.get("stage", "") for c in call_log)),
            "enforced_stages": list(set(c.get("stage", "") for c in enforced)),
        }
    except Exception as e:
        logger.warning("Could not extract enforcement summary: %s", e)

    # ── 6. Write report ───────────────────────────────────────────
    out_dir = Path("data/model_certification")
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"real_run_{result.run_id}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # ── 7. Print summary ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("REAL PIPELINE RUN COMPLETE")
    print("=" * 70)
    print(f"  Run ID:        {result.run_id}")
    print(f"  Domain:        {domain}")
    print(f"  Elapsed:       {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"  Papers found:  {report['papers_found']}")
    print(f"  Gaps found:    {report['gaps_found']}")
    print(f"  Ideas:         {report['ideas_generated']}")
    print(f"  Proposals:     {report['proposals_generated']}")
    print()
    print("  Stage Report:")
    for sr in report["stage_report"]:
        status_icon = "✓" if sr["status"] == "executed" else "✗"
        print(f"    {status_icon} {sr['name']:<28s} {sr['status']:<25s} {sr['elapsed_s']:.1f}s")
    print()

    if report["gaps"]:
        print("  Research Gaps:")
        for g in report["gaps"]:
            print(f"    [{g['confidence']:.2f}] {g['title'][:70]}")
        print()

    if report["ideas"]:
        print("  Research Ideas:")
        for i_data in report["ideas"]:
            nov = f"nov={i_data['novelty_score']:.2f}" if i_data.get("novelty_score") else ""
            feas = f"feas={i_data['feasibility_score']:.1f}" if i_data.get("feasibility_score") else ""
            print(f"    [{i_data['score']:.2f}] {i_data['title'][:70]} {nov} {feas}")
        print()

    enfc = report["enforcement_summary"]
    if enfc:
        print(f"  Enforcement: {enfc.get('enforced_calls', 0)} enforced / "
              f"{enfc.get('total_calls', 0)} total calls")
        print(f"  Enforced stages: {enfc.get('enforced_stages', [])}")
        print(f"  Degraded: {enfc.get('degraded_calls', 0)}")

    print()
    print(f"  Report: {report_path}")
    print("=" * 70)

    # Export paths
    if result.export_paths:
        print("  Exported files:")
        for idx, path in result.export_paths.items():
            print(f"    Proposal {idx}: {path}")


if __name__ == "__main__":
    asyncio.run(main())
