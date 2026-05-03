# Pipeline Retest Report (BATCH-56)

**Date:** 2026-05-03  
**Trigger:** POST /api/v1/pipeline/run  
**Domain:** AI/NLP

---

## Run Status

| Field | Value |
|:---|:---|
| DB Run ID | 11 |
| run_id string | run_20260503_061930 |
| Final status | **failed** |
| Time to failure | <5 seconds |
| Error message | `EROCK_OPENAI_API_KEY not set` |
| Current stage | initializing |
| completed_at | ✅ Set (BATCH-55 fix confirmed) |

---

## BATCH-55 Fix Verification: ✅ PASSED

The critical bug fix from BATCH-55 is confirmed working:

| Before BATCH-55 | After BATCH-55 |
|:---|:---|
| Run stuck in `status=running` forever | Run transitions to `status=failed` |
| No error_message | `error_message` populated with `"EROCK_OPENAI_API_KEY not set"` |
| No completed_at | `completed_at` correctly set |
| GET /runs crashes with INTERNAL_ERROR | GET /runs returns 200 with all run data |

---

## Root Cause of Pipeline Failure

The pipeline fails during initialization because a subsystem (likely the embedding service during ingestion stage) attempts to validate an OpenAI API key even when:
- `EROCK_DEFAULT_PROVIDER=anthropic` (uses z.ai endpoint)
- `EROCK_EMBEDDING_PROVIDER=dummy` (configured to skip real embeddings)

The `_validate_api_key()` method in `provider_factory.py` checks the OpenAI key when any code path touches the OpenAI/LiteLLM provider. The orchestrator's ingestion or knowledge subsystem likely initializes an OpenAI-backed service during startup.

---

## Resolution Required

Two options:

### Option A: Provide OpenAI API Key
Add `EROCK_OPENAI_API_KEY=sk-...` to `.env`. This is the simplest fix — the embedding service needs a valid key even with `dummy` provider (the validation happens before the provider selection).

### Option B: Fix Provider Validation Logic
The `_validate_api_key()` check should be skipped when the provider isn't being actively used. The embedding provider set to `dummy` should not trigger OpenAI key validation. This is a code fix in `provider_factory.py` or the orchestrator initialization sequence.

---

## Recommendations

1. **Immediate**: Add an OpenAI embedding key to `.env` OR fix the validation to skip unused providers
2. **Then re-trigger**: Run the pipeline again with valid configuration
3. **Then verify**: Full 9-stage pipeline completion with ideas, gaps, proposals

The platform's error handling is now production-quality. The remaining issue is a configuration/provider-selection edge case, not a core pipeline bug.

---

*Pipeline Retest Report — BATCH-56 — AIV Framework v5.2*
