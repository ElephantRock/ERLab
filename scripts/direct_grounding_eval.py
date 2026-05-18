"""Direct grounding evaluation for larger models.

Bypasses the certification runner to directly evaluate grounding metrics
for candidate models on evidence_table and adversarial_review stages.
"""

import asyncio
import json
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/model_certification/direct_grounding_eval.log"),
    ],
)
logger = logging.getLogger(__name__)

LMSTUDIO = "http://100.64.0.1:1234/v1"


def _load_eval_case(path: Path):
    """Load eval case YAML, return full data dict or None."""
    import yaml
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning("Failed to load %s: %s", path, e)
        return None


async def run_eval_for_model(model_id: str, cases: dict):
    """Run grounding eval cases for a single model."""
    import openai

    logger.info("=" * 70)
    logger.info("Model: %s", model_id)
    logger.info("=" * 70)

    client = openai.AsyncOpenAI(api_key="lm-studio", base_url=LMSTUDIO)
    results = {"model_id": model_id, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "cases": {}}

    for case_id, case_data in cases.items():
        if case_data is None:
            logger.warning("  Skipping %s: could not load", case_id)
            continue

        prompt = case_data.get("prompt_template", "")
        if not prompt:
            logger.warning("  Skipping %s: no prompt_template", case_id)
            continue

        gold_claims = case_data.get("gold", {}).get("claims", [])

        logger.info("  Running %s...", case_id)
        try:
            t0 = time.time()
            resp = await client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=case_data.get("output_token_budget", 2048),
                temperature=0.3,
            )
            elapsed = time.time() - t0
            raw_output = resp.choices[0].message.content or ""

            # Parse JSON
            parsed = None
            text = raw_output.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines: lines = lines[1:]
                if lines and lines[-1].strip().startswith("```"): lines = lines[:-1]
                text = "\n".join(lines).strip()
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                m = re.search(r'\[.*\]', text, re.DOTALL)
                if m:
                    try: parsed = json.loads(m.group())
                    except: pass

            # Compute grounding metrics
            grounding = {}
            if gold_claims:
                from backend.pipeline.model_certification.scorers.grounding import compute_grounding_metrics
                case_obj = type('Case', (), {
                    'stage': case_data.get('stage', ''),
                    'requires_grounding': case_data.get('requires_grounding', True),
                })()
                gold_obj = type('Gold', (), {
                    'claims': gold_claims,
                    'corpus_sources': case_data.get("gold", {}).get("corpus_sources", []),
                })()
                grounding = compute_grounding_metrics(raw_output, parsed, case_obj, gold_obj)

            case_result = {
                "elapsed_seconds": round(elapsed, 1),
                "output_length": len(raw_output),
                "json_valid": parsed is not None,
                "grounding_metrics": grounding,
                "output_preview": raw_output[:200],
            }
            results["cases"][case_id] = case_result
            gm_str = json.dumps({k: round(v, 3) for k, v in grounding.items()}) if grounding else "N/A"
            logger.info("    elapsed=%.1fs json=%s grounding=%s", elapsed, parsed is not None, gm_str)

        except Exception as e:
            results["cases"][case_id] = {"error": str(e)[:200]}
            logger.error("    Failed: %s", e)

    return results


async def main():
    eval_dir = Path("data/model_certification/eval_cases")

    # Load corpus-backed eval cases
    cases = {}
    for stage in ["evidence_table", "adversarial_review", "paper_synthesis", "proposal_synthesis"]:
        stage_dir = eval_dir / stage
        if not stage_dir.exists():
            continue
        for path in sorted(stage_dir.glob("*.yaml")):
            case_id = f"{stage}_{path.stem}"
            data = _load_eval_case(path)
            if data:
                cases[case_id] = data

    logger.info("Loaded %d eval cases", len(cases))

    # Test qwen2.5-14b-instruct (should be loaded)
    models_to_test = ["qwen2.5-14b-instruct"]

    all_results = {}
    for model_id in models_to_test:
        # Verify model is responding
        import httpx
        try:
            resp = httpx.post(f"{LMSTUDIO}/chat/completions", json={
                "model": model_id,
                "messages": [{"role": "user", "content": "Say OK"}],
                "max_tokens": 5,
            }, timeout=60)
            if resp.status_code != 200:
                logger.warning("Model %s not responding (status %d), skipping", model_id, resp.status_code)
                continue
        except Exception as e:
            logger.warning("Model %s not available: %s", model_id, e)
            continue

        result = await run_eval_for_model(model_id, cases)
        all_results[model_id] = result

    # Write results
    out_path = Path("data/model_certification/direct_grounding_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(all_results, indent=2, default=str), encoding="utf-8")

    # Print summary
    print("\n" + "=" * 70)
    print("Direct Grounding Evaluation Summary")
    print("=" * 70)
    for model_id, result in all_results.items():
        print(f"\n--- {model_id} ---")
        for case_id, cr in result.get("cases", {}).items():
            if "error" in cr:
                print(f"  {case_id}: ERROR - {cr['error'][:100]}")
            else:
                gm = cr.get("grounding_metrics", {})
                gm_str = json.dumps({k: round(v, 3) for k, v in gm.items()}) if gm else "N/A"
                print(f"  {case_id}: json={cr.get('json_valid')} len={cr.get('output_length', 0)} grounding={gm_str}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
