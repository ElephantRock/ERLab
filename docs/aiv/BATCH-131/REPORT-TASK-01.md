# REPORT-TASK-01 — Add LLM Verification Path + Prompt Template

**Batch:** BATCH-131  
**Task:** TASK-01  
**Status:** ✅ COMPLETE  
**Date:** 2026-05-09

---

## Summary

Added LLM-based claim verification to `WikiVerifier` alongside a closed-book verification prompt template. The verifier now uses `provider.complete()` for semantic claim verification when a provider is available, falling back to keyword overlap when the provider is `None` or when LLM calls fail.

## Files Modified

### `backend/pipeline/wiki/verifier.py` (MODIFIED)

**Changes:**
1. **Added `_verify_claim_with_llm()`** — async method that:
   - Loads the prompt template from `wiki_verification.md` (A-03)
   - Calls `self._provider.complete()` with claim + source text
   - Parses JSON response `{"supported": bool, "reasoning": str}` via `_parse_llm_response()`
   - Returns `{"supported": None, "reasoning": "LLM verification failed"}` on any failure

2. **Added `_parse_llm_response()`** — static method with robust JSON extraction:
   - Direct `json.loads()` first
   - Markdown code fence extraction
   - Brace-matching fallback
   - Graceful degradation to `supported=None` on all failures

3. **Enhanced `verify()` method** — now uses dual-path verification:
   - If `self._provider` is not None: try LLM first, fall back to keyword on failure (HB-01)
   - If `self._provider` is None: use keyword overlap for all claims
   - Unsupported claims from LLM include reasoning: `"claim — reasoning text"`
   - `quality_score = verified / total` regardless of authority (A-02)

4. **Renamed `_claim_supported` → `_claim_supported_keyword`** — kept as the keyword overlap implementation

5. **Added `_claim_supported` as alias** — delegates to `_claim_supported_keyword` for backward compatibility

6. **Added `_load_prompt_template()`** — lazy-loads and caches the prompt template from disk

### `backend/pipeline/wiki/prompts/wiki_verification.md` (NEW)

Closed-book verification prompt (HB-02):
- Explicitly instructs: "ONLY answer based on the source text"
- Provides `{claim}` and `{source_text}` placeholders
- Requires JSON output: `{"supported": true/false, "reasoning": "explanation"}`
- Contains "ONLY" and "source text" (satisfies HB-02 test)

## Acceptance Criteria Verification

| AC | Description | Status |
|:---|:------------|:-------|
| AC-01 | `_verify_claim_with_llm` returns `{"supported": bool, "reasoning": str}` | ✅ TEST-131-01-01 |
| AC-02 | `verify()` uses LLM when provider exists, keyword when not | ✅ TEST-131-01-02, 01-04 |
| AC-03 | Falls back gracefully on LLM failure (HB-01) | ✅ TEST-131-01-03 |
| AC-04 | Prompt template exists with closed-book instruction (HB-02) | ✅ TEST-131-01-05 |
| AC-05 | Original wiki entry is not modified (HB-03) | ✅ TEST-131-01-06 |
| AC-06 | Existing BATCH-123 tests still pass | ✅ TEST-131-02-01 |

## Hard Boundaries

- **HB-01**: ✅ Returns `WikiEntry` even if every LLM call fails (falls back to keyword)
- **HB-02**: ✅ Prompt explicitly instructs "ONLY answer based on the source text"
- **HB-03**: ✅ Uses `copy.deepcopy(wiki)` — original never modified
