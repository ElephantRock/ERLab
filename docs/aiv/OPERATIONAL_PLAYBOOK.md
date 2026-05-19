# Elephant Rock Platform — Operational Playbook

> **Purpose:** Never rediscover the same fact twice.  
> **Location:** `docs/aiv/OPERATIONAL_PLAYBOOK.md`  
> **Last updated:** 2026-05-20

---

## 1. LM Studio API Reference

**Base URL:** `http://100.64.0.1:1234` (GPU machine `gpc`)

| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| List models (with runtime config) | GET | `/api/v1/models` | — |
| Load model | POST | `/api/v1/models/load` | `{"model": "key", "context_length": N}` |
| Unload model | POST | `/api/v1/models/unload` | `{"instance_id": "key"}` |
| Chat (OpenAI compat) | POST | `/v1/chat/completions` | Standard OpenAI format |
| Embeddings | POST | `/v1/embeddings` | Standard OpenAI format |

**Critical defaults:**
- `context_length` defaults to **4096** on load — always specify explicitly
- `/v1/chat/completions` does NOT support `response_format` (returns 400)
- Model key format: `publisher/model-name` (e.g. `qwen/qwen3-4b-2507`)
- `max_context_length` in model info = hardware max; `context_length` in loaded_instances = runtime value

**Reload workflow (before pipeline runs):**
```bash
# 1. Unload current
curl -s -X POST http://100.64.0.1:1234/api/v1/models/unload \
  -H "Content-Type: application/json" \
  -d '{"instance_id": "qwen/qwen3-4b-2507"}'

# 2. Load with proper context
curl -s -X POST http://100.64.0.1:1234/api/v1/models/load \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen/qwen3-4b-2507", "context_length": 32768, "flash_attention": true}'

# 3. Verify
curl -s http://100.64.0.1:1234/api/v1/models | python -c "
import sys, json
for m in json.load(sys.stdin).get('models', []):
    if m.get('loaded_instances'):
        inst = m['loaded_instances'][0]
        print(f\"{m['key']}: ctx={inst['config']['context_length']}\")
"
```

---

## 2. Pipeline Run Checklist

Before running `scripts/real_pipeline_run.py`:

1. **Verify LM Studio reachable:** `curl -s http://100.64.0.1:1234/v1/models | head -5`
2. **Reload model with 32768 context** (see above)
3. **Confirm model loaded:** Check `context_length` in response
4. **Run:** `PYTHONPATH=. python scripts/real_pipeline_run.py`

The script now handles steps 1-3 automatically (reload + override).

---

## 3. Small Model (≤4B) Adaptations

| Issue | Solution |
|-------|----------|
| Context too small (4096) | Reload with `context_length: 32768` |
| Ideator prompt too verbose | Use minimal prompt (4 fields only) |
| Model wraps JSON in code fences | `extract_json` handles this automatically |
| `response_format: json_object` fails (400) | Fallback to plain text + `extract_json` |
| Gateway uses wrong context window | Override `_registry._capabilities` to match |
| Output truncated mid-JSON | Reduce `ideas_per_round`, `max_gaps`, or prompt detail |

**Gateway context override pattern:**
```python
caps_registry = orchestrator._gateway._registry
for key, cap in caps_registry._capabilities.items():
    if 'qwen3-4b' in key or 'glm' in key.lower():
        cap.context_window = 32768
        cap.safe_input_tokens = int(32768 * 0.70)
```

---

## 4. Known Model Capabilities

| Model | Params | Context | Speed | Notes |
|-------|--------|---------|-------|-------|
| qwen/qwen3-4b-2507 | 4B | 262K max, 32768 used | ~3s/call | Primary pipeline model |
| qwen2.5-14b-instruct | 14B | 32K | ~8s/call | Best grounding, fails fab gate |
| qwen/qwen3.5-9b | 9B | — | ~42s/call | Unparseable output, unusable |
| qwen3.5-27b | 27B | — | ~495s/call | Too slow (extreme offloading) |

**Grounding gates** (for certified/enforced stages): fab_rate < 0.05, support_rate > 0.70, unsupported_rate ≤ 0.20  
**No local model passes all gates.** Cloud LLM (Anthropic/OpenAI) needed for grounded stages.

---

## 5. Hardware Reference

| Machine | GPU | Role | Access |
|---------|-----|------|--------|
| gpc (100.64.0.1) | RTX 3080 Ti 12GB | LM Studio server | Tailscale/LAN |
| Local (this machine) | AMD Radeon 780M 2GB | Dev, embedding only | localhost |

---

## 6. Common Failure Modes & Fixes

| Symptom | Cause | Fix |
|---------|-------|-----|
| `400 Bad Request` on chat | `response_format: json_object` not supported | Use plain text + `extract_json` |
| `n_keep >= n_ctx` error | Prompt exceeds context_length | Reload model with larger context |
| `OVERFLOW` in token budget | Gateway context_window too small | Override `_registry._capabilities` |
| JSON truncated mid-value | Output too long for max_tokens | Increase max_tokens or reduce prompt detail |
| `Could not extract JSON` | Code fence wrapping or truncation | `extract_json` handles fences; truncation needs prompt reduction |
| 0 ideas generated | Ideator prompt too complex for model | Use minimal prompt with fewer fields |
| Ideas not persisted | Original prompt override after orchestrator init | Write prompt file BEFORE building orchestrator |
| Stale `.pyc` after edit | Python bytecode cache | `rm -rf backend/**/__pycache__/` |

---

## 7. Key Commits

| Hash | Description |
|------|-------------|
| `569ce1c` | First successful real pipeline run (2 proposals) |
| `d049455` | Context window override + truncated JSON repair |
| `c502c7a` | extract_json fallback + first real run report |
| `6776080` | CLI fix + direct grounding eval script |
| `360207b` | Candidate manifests for larger models |
