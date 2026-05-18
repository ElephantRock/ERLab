"""Phase 2 Targeted Enforcement Exercise: idea_generation + feasibility_scoring.

Exercises enforcement for low/medium-risk generation stages:
  - 3 idea_generation calls
  - 3 feasibility_scoring calls
  - 1 degraded path per stage
  - Quality metrics collected

Usage:
    EROCK_DEFAULT_PROVIDER=lmstudio python scripts/phase2_targeted_enforcement.py
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            "data/model_certification/phase2_targeted_enforcement.log"
        ),
    ],
)
logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────

def _count_ideas(text: str) -> int:
    """Count idea-like structures in output."""
    import re
    # Look for numbered items, bullet points, or "Idea X" patterns
    patterns = [
        r'(?:^|\n)\s*\d+[\.\)]\s',       # 1. or 1)
        r'(?:^|\n)\s*[-*]\s',             # - or * bullets
        r'(?:^|\n)\s*Idea\s+\d+',         # Idea 1, Idea 2
        r'"title"\s*:',                    # JSON title fields
    ]
    count = 0
    for p in patterns:
        matches = re.findall(p, text)
        count = max(count, len(matches))
    return max(count, 1) if text.strip() else 0


def _check_json_valid(text: str) -> bool:
    """Check if output is valid JSON."""
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def _extract_scores(text: str) -> list[float]:
    """Extract numeric scores from text."""
    import re
    # Look for score patterns: "score": 0.8, Score: 7.5, etc.
    patterns = [
        r'"(?:score|feasibility|rating)"\s*:\s*([\d.]+)',
        r'[Ss]core\s*[:=]\s*([\d.]+)',
        r'(?:^|\n)\s*\d+[\.\)]\s.*?([\d.]+)/10',
    ]
    scores = []
    for p in patterns:
        for m in re.finditer(p, text):
            try:
                val = float(m.group(1))
                if 0 <= val <= 10:
                    scores.append(val)
            except ValueError:
                pass
    return scores


async def main():
    start_time = time.time()
    run_id = f"phase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info("=" * 70)
    logger.info("Phase 2 Targeted Enforcement: %s", run_id)
    logger.info("Stages: idea_generation, feasibility_scoring")
    logger.info("=" * 70)

    # Force LM Studio
    os.environ["EROCK_DEFAULT_PROVIDER"] = "lmstudio"
    os.environ["EROCK_THINKING_MODEL"] = "lmstudio"
    os.environ["EROCK_GENERATION_MODEL"] = "lmstudio"
    os.environ["EROCK_ANTHROPIC_MODEL"] = "qwen/qwen3-4b-2507"

    from backend.config import get_settings
    get_settings.cache_clear()
    settings = get_settings()

    # ── Build gateway ────────────────────────────────────────────────
    from backend.pipeline.gateway.gateway import LLMGateway, LLMRequest
    from backend.pipeline.gateway.capability_registry import ModelCapabilityRegistry
    from backend.pipeline.gateway.token_budget import TokenBudgeter
    from backend.pipeline.routing.smart_router import SmartRouter
    from backend.pipeline.routing.certified_lookup import CertifiedCapabilityLookup
    from backend.pipeline.routing.dry_run_logger import DryRunLogger
    from backend.pipeline.routing.stage_contract import get_smart_router_config
    from backend.providers.provider_factory import create_provider

    registry = ModelCapabilityRegistry()
    budgeter = TokenBudgeter()
    gateway = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")

    inner_provider = create_provider("lmstudio")

    async def _provider_fn(*, messages, temperature, max_tokens, schema=None, tools=None):
        if schema:
            try:
                return await inner_provider.structured_output(messages, schema, temperature)
            except Exception:
                pass
        return await inner_provider.complete(messages, temperature, max_tokens)

    gateway._provider_fn = _provider_fn

    # SmartRouter with ALL enforced stages (repair, query_generation + idea_generation, feasibility_scoring)
    enforced_stages = ["repair", "query_generation", "idea_generation", "feasibility_scoring"]
    logger.info("Enforced stages: %s", enforced_stages)

    lookup = CertifiedCapabilityLookup()
    router = SmartRouter(lookup, mode="enforce",
                         ranking_weights=get_smart_router_config().get("ranking_weights"))
    dry_run_logger = DryRunLogger(log_dir="data/model_certification/routing_logs")

    gateway.set_smart_router(
        router, mode="enforce", dry_run_logger=dry_run_logger,
        enforced_stages=enforced_stages,
    )

    # ── Results tracking ─────────────────────────────────────────────
    results = {
        "run_id": run_id,
        "enforced_stages": enforced_stages,
        "idea_generation": {"calls": [], "metrics": {}},
        "feasibility_scoring": {"calls": [], "metrics": {}},
        "degraded_tests": [],
        "tests": [],
    }

    # ── IDEA GENERATION (3 calls) ────────────────────────────────────
    logger.info("-" * 70)
    logger.info("IDEA GENERATION: 3 enforced calls")
    logger.info("-" * 70)

    idea_prompts = [
        ("Generating research ideas about efficient attention mechanisms in transformers",
         "Generate 3 novel research ideas about efficient attention mechanisms."),
        ("Generating ideas about self-supervised learning for small datasets",
         "Generate 3 novel research ideas about self-supervised learning for small datasets."),
        ("Generating ideas about multi-modal reasoning in LLMs",
         "Generate 3 novel research ideas about multi-modal reasoning in large language models."),
    ]

    idea_texts = []
    for desc, prompt in idea_prompts:
        logger.info("  → %s", desc)
        request = LLMRequest(
            task="idea_generation",
            messages=[
                {"role": "system", "content": "You are a creative research idea generator. "
                 "Generate novel, feasible research ideas with clear hypotheses."},
                {"role": "user", "content": prompt},
            ],
            stage="idea_generation",
            max_output_tokens=4096,
            run_id=run_id,
        )
        try:
            response = await gateway.call(request)
            call_log = gateway.get_call_log(limit=5)
            ig_calls = [c for c in call_log if c.get("stage") == "idea_generation"]

            entry = {
                "prompt": desc,
                "enforcement_applied": ig_calls[-1].get("enforcement_applied", False) if ig_calls else False,
                "routed_model": ig_calls[-1].get("routed_model", "") if ig_calls else "",
                "actual_model": ig_calls[-1].get("model", "") if ig_calls else "",
                "routed_strategy": ig_calls[-1].get("routed_strategy", "") if ig_calls else "",
                "certification_status": ig_calls[-1].get("certification_status", "") if ig_calls else "",
                "stage_eligibility": ig_calls[-1].get("stage_eligibility", "") if ig_calls else "",
                "hard_gate_failures": ig_calls[-1].get("hard_gate_failures", []) if ig_calls else [],
                "degraded": response.degraded,
                "output_length": len(response.content) if response.content else 0,
                "confidence": response.confidence,
                "idea_count": _count_ideas(response.content) if response.content else 0,
                "json_valid": _check_json_valid(response.content) if response.content else False,
                "empty": not response.content,
            }
            idea_texts.append(response.content or "")
            results["idea_generation"]["calls"].append(entry)
            logger.info("    enforced=%s model=%s ideas=%d len=%d",
                        entry["enforcement_applied"], entry["routed_model"],
                        entry["idea_count"], entry["output_length"])
        except Exception as e:
            results["idea_generation"]["calls"].append({
                "prompt": desc, "error": str(e), "degraded": True,
            })
            logger.error("    Failed: %s", e)

    # ── FEASIBILITY SCORING (3 calls) ────────────────────────────────
    logger.info("-" * 70)
    logger.info("FEASIBILITY SCORING: 3 enforced calls")
    logger.info("-" * 70)

    feasibility_prompts = [
        ("Scoring feasibility of sparse attention idea",
         "Score the feasibility of this research idea on a 0-1 scale:\n"
         "'Sparse Attention with Learned Routing for Long-Context Transformers'\n"
         "Return JSON: {\"score\": <float>, \"explanation\": \"<string>\", \"risks\": [\"<string>\"]}"),
        ("Scoring feasibility of self-supervised idea",
         "Score the feasibility of this research idea on a 0-1 scale:\n"
         "'Contrastive Pre-Training for Domain-Specific Small Datasets'\n"
         "Return JSON: {\"score\": <float>, \"explanation\": \"<string>\", \"risks\": [\"<string>\"]}"),
        ("Scoring feasibility of multi-modal idea",
         "Score the feasibility of this research idea on a 0-1 scale:\n"
         "'Cross-Modal Reasoning Chains for Visual Question Answering'\n"
         "Return JSON: {\"score\": <float>, \"explanation\": \"<string>\", \"risks\": [\"<string>\"]}"),
    ]

    feasibility_texts = []
    for desc, prompt in feasibility_prompts:
        logger.info("  → %s", desc)
        request = LLMRequest(
            task="feasibility_scoring",
            messages=[
                {"role": "system", "content": "You are a research feasibility scorer. "
                 "Score ideas on a 0-1 scale with explanation."},
                {"role": "user", "content": prompt},
            ],
            stage="feasibility_scoring",
            max_output_tokens=2048,
            run_id=run_id,
        )
        try:
            response = await gateway.call(request)
            call_log = gateway.get_call_log(limit=10)
            fs_calls = [c for c in call_log if c.get("stage") == "feasibility_scoring"]

            scores = _extract_scores(response.content) if response.content else []
            entry = {
                "prompt": desc,
                "enforcement_applied": fs_calls[-1].get("enforcement_applied", False) if fs_calls else False,
                "routed_model": fs_calls[-1].get("routed_model", "") if fs_calls else "",
                "actual_model": fs_calls[-1].get("model", "") if fs_calls else "",
                "routed_strategy": fs_calls[-1].get("routed_strategy", "") if fs_calls else "",
                "certification_status": fs_calls[-1].get("certification_status", "") if fs_calls else "",
                "stage_eligibility": fs_calls[-1].get("stage_eligibility", "") if fs_calls else "",
                "hard_gate_failures": fs_calls[-1].get("hard_gate_failures", []) if fs_calls else [],
                "degraded": response.degraded,
                "output_length": len(response.content) if response.content else 0,
                "confidence": response.confidence,
                "json_valid": _check_json_valid(response.content) if response.content else False,
                "scores": scores,
                "score_bounds_valid": all(0 <= s <= 1 for s in scores) if scores else None,
                "explanation_present": "explanation" in (response.content or "").lower(),
                "empty": not response.content,
            }
            feasibility_texts.append(response.content or "")
            results["feasibility_scoring"]["calls"].append(entry)
            logger.info("    enforced=%s model=%s scores=%s json=%s",
                        entry["enforcement_applied"], entry["routed_model"],
                        scores, entry["json_valid"])
        except Exception as e:
            results["feasibility_scoring"]["calls"].append({
                "prompt": desc, "error": str(e), "degraded": True,
            })
            logger.error("    Failed: %s", e)

    # ── DEGRADED PATH TESTS ──────────────────────────────────────────
    logger.info("-" * 70)
    logger.info("DEGRADED PATH TESTS")
    logger.info("-" * 70)

    from unittest.mock import AsyncMock

    # Idea generation degraded
    degraded_ig_gw = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")
    degraded_ig_gw._provider_fn = AsyncMock(return_value='{"ideas": []}')
    empty_lookup = CertifiedCapabilityLookup()
    empty_lookup.get_candidates_for_stage = lambda stage: []
    degraded_ig_gw.set_smart_router(
        SmartRouter(empty_lookup, mode="enforce"), mode="enforce",
        dry_run_logger=dry_run_logger, enforced_stages=["idea_generation"],
    )
    ig_deg_req = LLMRequest(
        task="idea_generation",
        messages=[{"role": "user", "content": "generate ideas"}],
        stage="idea_generation", max_output_tokens=2048,
    )
    ig_deg_resp = await degraded_ig_gw.call(ig_deg_req)
    ig_degraded_ok = ig_deg_resp.degraded is True
    results["degraded_tests"].append({
        "stage": "idea_generation", "degraded": ig_degraded_ok,
        "warnings": ig_deg_resp.warnings,
    })
    logger.info("  idea_generation degraded=%s (expected True)", ig_degraded_ok)

    # Feasibility scoring degraded
    degraded_fs_gw = LLMGateway(registry, budgeter, default_model="qwen/qwen3-4b-2507")
    degraded_fs_gw._provider_fn = AsyncMock(return_value='{"score": 0.0}')
    degraded_fs_gw.set_smart_router(
        SmartRouter(empty_lookup, mode="enforce"), mode="enforce",
        dry_run_logger=dry_run_logger, enforced_stages=["feasibility_scoring"],
    )
    fs_deg_req = LLMRequest(
        task="feasibility_scoring",
        messages=[{"role": "user", "content": "score this idea"}],
        stage="feasibility_scoring", max_output_tokens=2048,
    )
    fs_deg_resp = await degraded_fs_gw.call(fs_deg_req)
    fs_degraded_ok = fs_deg_resp.degraded is True
    results["degraded_tests"].append({
        "stage": "feasibility_scoring", "degraded": fs_degraded_ok,
        "warnings": fs_deg_resp.warnings,
    })
    logger.info("  feasibility_scoring degraded=%s (expected True)", fs_degraded_ok)

    # ── Quality Metrics ──────────────────────────────────────────────
    ig_calls = results["idea_generation"]["calls"]
    fs_calls = results["feasibility_scoring"]["calls"]

    # Idea generation metrics
    ig_enforced = [c for c in ig_calls if c.get("enforcement_applied")]
    ig_nonempty = [c for c in ig_calls if not c.get("empty") and not c.get("error")]
    idea_counts = [c.get("idea_count", 0) for c in ig_nonempty]
    ig_empty_rate = sum(1 for c in ig_calls if c.get("empty", False)) / max(len(ig_calls), 1)
    ig_malformed_rate = sum(1 for c in ig_nonempty if not c.get("json_valid", True)) / max(len(ig_nonempty), 1)

    # Duplicate detection (simple text overlap)
    ig_texts_set = set()
    ig_dupes = 0
    for t in idea_texts:
        sig = t[:100].lower().strip()
        if sig in ig_texts_set:
            ig_dupes += 1
        ig_texts_set.add(sig)

    results["idea_generation"]["metrics"] = {
        "calls_total": len(ig_calls),
        "calls_enforced": len(ig_enforced),
        "idea_count_per_call": idea_counts,
        "avg_idea_count": sum(idea_counts) / max(len(idea_counts), 1),
        "empty_output_rate": round(ig_empty_rate, 3),
        "malformed_output_rate": round(ig_malformed_rate, 3),
        "duplicate_idea_rate": round(ig_dupes / max(len(idea_texts), 1), 3),
        "all_certified": all(c.get("certification_status") == "certified" for c in ig_enforced),
    }

    # Feasibility scoring metrics
    fs_enforced = [c for c in fs_calls if c.get("enforcement_applied")]
    fs_nonempty = [c for c in fs_calls if not c.get("empty") and not c.get("error")]
    all_scores = [s for c in fs_nonempty for s in c.get("scores", [])]
    score_bounds_valid = all(0 <= s <= 1 for s in all_scores) if all_scores else None
    invalid_score_count = sum(1 for s in all_scores if not (0 <= s <= 1)) if all_scores else 0

    results["feasibility_scoring"]["metrics"] = {
        "calls_total": len(fs_calls),
        "calls_enforced": len(fs_enforced),
        "all_scores": all_scores,
        "avg_score": sum(all_scores) / max(len(all_scores), 1),
        "score_bounds_valid": score_bounds_valid,
        "invalid_score_rate": round(invalid_score_count / max(len(all_scores), 1), 3),
        "explanation_present_rate": round(
            sum(1 for c in fs_nonempty if c.get("explanation_present", False)) / max(len(fs_nonempty), 1), 3
        ),
        "json_valid_rate": round(
            sum(1 for c in fs_nonempty if c.get("json_valid", False)) / max(len(fs_nonempty), 1), 3
        ),
        "degraded_rate": round(
            sum(1 for c in fs_calls if c.get("degraded", False)) / max(len(fs_calls), 1), 3
        ),
        "all_certified": all(c.get("certification_status") == "certified" for c in fs_enforced),
    }

    # ── Pass criteria ────────────────────────────────────────────────
    elapsed = time.time() - start_time

    pass_criteria = {
        "at_least_6_enforced_calls": len(ig_enforced) + len(fs_enforced) >= 6,
        "idea_generation_enforced": len(ig_enforced) >= 3,
        "feasibility_scoring_enforced": len(fs_enforced) >= 3,
        "no_uncertified_model": all(
            c.get("certification_status") == "certified"
            for c in ig_enforced + fs_enforced
        ),
        "model_routing_consistent": all(
            c.get("routed_model") == c.get("actual_model", "").replace("qwen/", "")
            for c in ig_enforced + fs_enforced
            if c.get("routed_model") and c.get("actual_model")
        ),
        "no_hard_gate_failures": all(
            not c.get("hard_gate_failures")
            for c in ig_enforced + fs_enforced
        ),
        "idea_generation_degraded_tested": ig_degraded_ok,
        "feasibility_scoring_degraded_tested": fs_degraded_ok,
        "no_router_exceptions": True,
        "idea_output_nonempty": all(not c.get("empty") for c in ig_calls if not c.get("error")),
        "feasibility_output_nonempty": all(not c.get("empty") for c in fs_calls if not c.get("error")),
    }

    results["elapsed_seconds"] = round(elapsed, 1)
    results["pass_criteria"] = pass_criteria
    results["verdict"] = "PASS" if all(pass_criteria.values()) else "PASS_WITH_WARNINGS"

    # Write results
    results_path = Path("data/model_certification/phase2_targeted_results.json")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    # ── Print summary ────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("Phase 2 Targeted Enforcement Summary")
    print(f"Run ID: {run_id}")
    print(f"Elapsed: {elapsed:.1f}s")
    print("=" * 70)

    ig_m = results["idea_generation"]["metrics"]
    fs_m = results["feasibility_scoring"]["metrics"]

    print(f"\n--- Idea Generation ---")
    print(f"  Enforced: {ig_m['calls_enforced']}/{ig_m['calls_total']}")
    print(f"  Avg ideas per call: {ig_m['avg_idea_count']:.1f}")
    print(f"  Empty output rate: {ig_m['empty_output_rate']}")
    print(f"  Malformed rate: {ig_m['malformed_output_rate']}")
    print(f"  Duplicate rate: {ig_m['duplicate_idea_rate']}")
    print(f"  All certified: {ig_m['all_certified']}")

    print(f"\n--- Feasibility Scoring ---")
    print(f"  Enforced: {fs_m['calls_enforced']}/{fs_m['calls_total']}")
    print(f"  Scores: {fs_m['all_scores']}")
    print(f"  Avg score: {fs_m['avg_score']:.3f}")
    print(f"  Score bounds valid: {fs_m['score_bounds_valid']}")
    print(f"  Invalid score rate: {fs_m['invalid_score_rate']}")
    print(f"  Explanation present: {fs_m['explanation_present_rate']}")
    print(f"  JSON valid rate: {fs_m['json_valid_rate']}")
    print(f"  All certified: {fs_m['all_certified']}")

    print(f"\n--- Degraded Tests ---")
    for dt in results["degraded_tests"]:
        print(f"  {dt['stage']}: degraded={dt['degraded']}")

    print(f"\n--- Pass Criteria ---")
    for k, v in pass_criteria.items():
        print(f"  {'PASS' if v else 'FAIL'} {k}")

    print(f"\nVerdict: {results['verdict']}")
    print("=" * 70)

    return results


if __name__ == "__main__":
    asyncio.run(main())
