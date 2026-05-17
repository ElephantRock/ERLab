#!/usr/bin/env python3
"""Test LM Studio structured output (response_format json_schema) support.

Tests three schemas across three models, recording:
  - request success rate
  - parse success rate
  - schema valid rate
  - latency
  - failure messages
  - strict=true behavior
"""

import asyncio
import json
import time
import statistics
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema definitions (mirrors config/schemas/*.schema.json)
# ---------------------------------------------------------------------------

SCHEMAS = {
    "smoke_test": {
        "type": "object",
        "properties": {
            "status": {"type": "string"}
        },
        "required": ["status"],
        "additionalProperties": False,
    },
    "structured_claim": {
        "type": "object",
        "properties": {
            "claim_type": {"type": "string"},
            "claim_text": {"type": "string"},
            "section": {"type": "string"},
            "evidence_level": {"type": "string", "enum": ["strong", "moderate", "weak", "none"]},
            "source_citations": {
                "type": "array",
                "items": {"type": "string"}
            }
        },
        "required": ["claim_type", "claim_text", "section", "evidence_level"],
        "additionalProperties": True,
    },
    "repair": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["keep", "remove", "mark_speculative", "reclassify", "split"]},
            "claim_id": {"type": "string"},
            "reason": {"type": "string"},
            "new_type": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        },
        "required": ["action", "claim_id", "reason"],
        "additionalProperties": True,
    },
}

PROMPTS = {
    "smoke_test": "Return a JSON object with a single field 'status' set to 'ok'.",
    "structured_claim": (
        "Extract a structured claim from this text: "
        "'Transformer attention mechanisms significantly improve performance on long-document tasks "
        "(Vaswani et al., 2017). The method uses self-attention to process sequences in parallel.' "
        "Return JSON with claim_type, claim_text, section, evidence_level, and source_citations."
    ),
    "repair": (
        "Given claim CLM-042 'BERT achieves state-of-the-art on all NLP benchmarks' which overclaims, "
        "produce a repair decision JSON with action='reclassify', claim_id='CLM-042', "
        "reason='Overclaim: BERT is not SOTA on all benchmarks', and confidence=0.85."
    ),
}

MODELS = [
    "qwen/qwen3-4b-2507",
    "qwen3.5-0.8b",
    "qwen2.5-14b-instruct",
]

BASE_URL = "http://100.64.0.1:1234/v1"

# ---------------------------------------------------------------------------
# Test modes
# ---------------------------------------------------------------------------

async def test_prompted(client, model: str, schema_name: str, schema: dict, prompt: str):
    """Standard prompted JSON — no response_format."""
    t0 = time.perf_counter()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt + "\n\nReturn ONLY valid JSON, no other text."}],
        max_tokens=1024,
        temperature=0.3,
    )
    elapsed = time.perf_counter() - t0
    text = (resp.choices[0].message.content or "").strip()
    return _evaluate(text, schema, elapsed)


async def test_structured(client, model: str, schema_name: str, schema: dict, prompt: str):
    """Structured output via response_format.type=json_schema."""
    t0 = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                },
            },
        )
        elapsed = time.perf_counter() - t0
        text = (resp.choices[0].message.content or "").strip()
        return _evaluate(text, schema, elapsed)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "elapsed": elapsed,
            "request_ok": False,
            "parse_ok": False,
            "schema_ok": False,
            "error": str(e)[:200],
        }


async def test_structured_strict_bool(client, model: str, schema_name: str, schema: dict, prompt: str):
    """Structured output with strict=true (boolean)."""
    t0 = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                    "strict": True,
                },
            },
        )
        elapsed = time.perf_counter() - t0
        text = (resp.choices[0].message.content or "").strip()
        return _evaluate(text, schema, elapsed)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "elapsed": elapsed,
            "request_ok": False,
            "parse_ok": False,
            "schema_ok": False,
            "error": str(e)[:200],
        }


async def test_structured_strict_string(client, model: str, schema_name: str, schema: dict, prompt: str):
    """Structured output with strict='true' (string)."""
    t0 = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema,
                    "strict": "true",
                },
            },
        )
        elapsed = time.perf_counter() - t0
        text = (resp.choices[0].message.content or "").strip()
        return _evaluate(text, schema, elapsed)
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "elapsed": elapsed,
            "request_ok": False,
            "parse_ok": False,
            "schema_ok": False,
            "error": str(e)[:200],
        }


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _evaluate(text: str, schema: dict, elapsed: float) -> dict:
    result = {
        "elapsed": elapsed,
        "request_ok": True,
        "parse_ok": False,
        "schema_ok": False,
        "error": None,
    }
    if not text:
        result["error"] = "Empty response"
        return result

    # Try parse
    try:
        parsed = json.loads(text)
        result["parse_ok"] = True
    except json.JSONDecodeError:
        # Try stripping fences
        cleaned = text
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines:
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            parsed = json.loads(cleaned)
            result["parse_ok"] = True
        except json.JSONDecodeError as e:
            result["error"] = f"JSON parse error: {e}"
            return result

    # Schema validation
    if not isinstance(parsed, dict):
        result["error"] = f"Parsed JSON is {type(parsed).__name__}, not object"
        return result

    # Check required fields
    required = schema.get("required", [])
    missing = [f for f in required if f not in parsed]
    if missing:
        result["error"] = f"Missing required fields: {missing}"
        return result

    # Check enum constraints
    props = schema.get("properties", {})
    for key, val in parsed.items():
        if key in props:
            prop_def = props[key]
            if "enum" in prop_def and val not in prop_def["enum"]:
                result["error"] = f"Field '{key}' value '{val}' not in enum {prop_def['enum']}"
                return result

    result["schema_ok"] = True
    return result


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def main():
    import openai

    client = openai.AsyncOpenAI(api_key="lm-studio", base_url=BASE_URL)

    results = []
    N_TRIALS = 3  # repeat each test 3 times for stability

    for model in MODELS:
        print(f"\n{'='*70}")
        print(f"Model: {model}")
        print(f"{'='*70}")

        for schema_name in SCHEMAS:
            schema = SCHEMAS[schema_name]
            prompt = PROMPTS[schema_name]

            modes = {
                "prompted": test_prompted,
                "structured": test_structured,
                "strict_bool": test_structured_strict_bool,
                "strict_string": test_structured_strict_string,
            }

            for mode_name, mode_fn in modes.items():
                trials = []
                for trial in range(N_TRIALS):
                    r = await mode_fn(client, model, schema_name, schema, prompt)
                    trials.append(r)
                    results.append({
                        "model": model,
                        "schema": schema_name,
                        "mode": mode_name,
                        "trial": trial,
                        **r,
                    })

                # Aggregate
                req_ok = sum(1 for t in trials if t.get("request_ok"))
                parse_ok = sum(1 for t in trials if t.get("parse_ok"))
                schema_ok = sum(1 for t in trials if t.get("schema_ok"))
                latencies = [t["elapsed"] for t in trials]
                errors = [t.get("error", "") for t in trials if t.get("error")]

                req_rate = req_ok / N_TRIALS
                parse_rate = parse_ok / N_TRIALS
                schema_rate = schema_ok / N_TRIALS
                avg_lat = statistics.mean(latencies)

                status = "✅" if schema_rate == 1.0 else "⚠️" if schema_rate > 0 else "❌"
                print(
                    f"  {schema_name:20s} | {mode_name:14s} | "
                    f"req={req_rate:.0%} parse={parse_rate:.0%} schema={schema_rate:.0%} | "
                    f"lat={avg_lat:.1f}s {status}"
                )
                if errors:
                    unique_errors = list(set(errors))[:3]
                    for e in unique_errors:
                        print(f"    ↳ {e[:120]}")

    # Summary table
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"{'Model':<30s} | {'Mode':<14s} | {'smoke':>5s} | {'claim':>5s} | {'repair':>5s} | {'Avg lat':>7s}")
    print("-" * 70)

    for model in MODELS:
        for mode in ["prompted", "structured", "strict_bool", "strict_string"]:
            rates = {}
            lats = []
            for schema_name in SCHEMAS:
                matching = [r for r in results
                            if r["model"] == model
                            and r["schema"] == schema_name
                            and r["mode"] == mode]
                if matching:
                    rates[schema_name] = sum(1 for r in matching if r.get("schema_ok")) / len(matching)
                    lats.extend([r["elapsed"] for r in matching])

            short_model = model.split("/")[-1][:28]
            avg_lat = statistics.mean(lats) if lats else 0
            smoke = f"{rates.get('smoke_test', 0):.0%}"
            claim = f"{rates.get('structured_claim', 0):.0%}"
            repair = f"{rates.get('repair', 0):.0%}"
            print(f"{short_model:<30s} | {mode:<14s} | {smoke:>5s} | {claim:>5s} | {repair:>5s} | {avg_lat:>6.1f}s")
        print()

    # Structured support verdict
    print(f"{'='*70}")
    print("STRUCTURED OUTPUT SUPPORT")
    print(f"{'='*70}")
    for model in MODELS:
        structured_ok = any(
            r.get("schema_ok") and r["mode"] == "structured"
            for r in results
            if r["model"] == model
        )
        strict_bool_ok = any(
            r.get("request_ok") and r["mode"] == "strict_bool"
            for r in results
            if r["model"] == model
        )
        strict_string_ok = any(
            r.get("request_ok") and r["mode"] == "strict_string"
            for r in results
            if r["model"] == model
        )
        short = model.split("/")[-1]
        print(f"  {short:28s} | structured={structured_ok!s:5s} | strict_bool={strict_bool_ok!s:5s} | strict_str={strict_string_ok!s:5s}")


if __name__ == "__main__":
    asyncio.run(main())
