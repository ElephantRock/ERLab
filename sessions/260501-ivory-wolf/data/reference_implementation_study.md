# Reference Implementation Study Report

**Date**: 2026-05-09  
**Source**: `pasted-text-1.txt` — External reference implementation for Phase 9 Quality Hardening  
**Scope**: BATCH-131 through BATCH-136 (5 modules + quality validation)

---

## Executive Summary

The reference document proposes an **alternative architecture** for the same 5 modules we already deepened in Phase 9.1 (B131–B136). Both implementations share the same core approach (LLM-first with heuristic fallback), but differ significantly in **data model richness, prompt sophistication, and test philosophy**.

**Verdict**: The reference is a **design document for a different project**, not a direct improvement to our codebase. It proposes modules that would replace our existing ones entirely rather than enhancing them. Our implementation integrates into the Elephant Rock pipeline; the reference assumes a standalone agent architecture.

---

## Module-by-Module Comparison

### BATCH-131: WikiVerifier

| Aspect | Reference | Our Implementation |
|:-------|:----------|:-------------------|
| **Class name** | `WikiVerifier` | `WikiVerifier` (same) |
| **Verification states** | 5 states: `SUPPORTED`, `UNSUPPORTED`, `PARTIALLY_SUPPORTED`, `UNCLEAR`, `ERROR` | Binary: `supported=True/False` |
| **Data model** | `ClaimVerification` dataclass (claim, status, reasoning, confidence, source_evidence, llm_used) | Returns `WikiEntry` with `quality_score` + `unsupported_claims` list |
| **Source truncation** | 15,000 chars | 3,000 chars |
| **Prompt** | Inline in code, detailed role + criteria + JSON schema | External file `wiki_verification.md`, closed-book policy |
| **Keyword threshold** | 0.4 (same) | 0.4 (same) |
| **Confidence cap** | Keyword capped at 0.7 | No confidence scoring |
| **Verification metadata** | `_verification` dict with timestamp, version, needs_human_review | `quality_score` + `unsupported_claims` |
| **DB integration** | None (standalone) | None (standalone) |

**Reference advantages:**
- 5-state verification (PARTIALLY_SUPPORTED and UNCLEAR are useful)
- `ClaimVerification` dataclass preserves per-claim evidence and confidence
- 15K char source context (5x more than ours)
- `needs_human_review` flag based on unsupported ratio
- Keyword confidence capped at 0.7 (prevents overconfidence)

**Our advantages:**
- External prompt file (easier to modify without code changes)
- Closed-book policy explicitly enforced in prompt
- Immutable input (HB-03 deep copy)
- Integrated with WikiEntry model (pipeline-compatible)
- Real-LLM validated: flagged 2/2 quantum fabrications correctly

---

### BATCH-132: ContradictionDetector

| Aspect | Reference | Our Implementation |
|:-------|:----------|:-------------------|
| **Contradiction types** | 5: GENUINE, DIFFERENT_CONDITIONS, INCOMPARABLE, SAME_RESULT, UNCERTAIN | Binary: `is_genuine=True/False/None` |
| **Data model** | `ContradictionVerification` (8 fields including possible_explanations, resolution_suggested) | `ContradictionCandidate` (6 fields: claim_a, claim_b, metric, dataset, value_a, value_b, is_genuine, explanation) |
| **DB queries** | SQL JOIN on claims table | In-memory: filters RESULT claims by same dataset+metric |
| **LLM prompt** | 30-line structured prompt with per-claim details (language_pair, task, details) | 15-line prompt from external file |
| **Resolution** | Checks for reconciliation papers | No reconciliation check |
| **Gap creation** | Creates gap entries from contradictions | Returns candidates only (orchestrator creates gaps) |

**Reference advantages:**
- Richer classification (5 types vs binary)
- `possible_explanations` and `resolution_suggested` fields
- SQL-based candidate finding (scalable)
- Reconciliation paper checking
- Creates actionable gap entries directly

**Our advantages:**
- External prompt file
- Pipeline-integrated (works with Claim objects)
- Event-loop-safe (async with loop detection)
- Simpler model = fewer integration points to break
- Real-LLM validated: correctly identified EN→DE vs FR→EN as `different_conditions`

---

### BATCH-133: MethodProblemDetector

| Aspect | Reference | Our Implementation |
|:-------|:----------|:-------------------|
| **Assessment** | `ApplicabilityAssessment` (12 fields: score, requires_adaptation, adaptations_needed, estimated_improvement, rationale, risk_factors, confidence) | `MethodProblemGap` (5 fields: method_name, method_paper_id, problem_dataset, applicability_score, reasoning) |
| **Scoring granularity** | 0.0-1.0 with specific criteria bands | 0.0-1.0 (same range) |
| **Prompt** | Detailed with method category, modality, assumptions, constraints, SOTA | Applicability scoring with method+dataset |
| **Fallback** | Heuristic with modality matching + task compatibility | Uniform 0.5 (less informative) |
| **DB queries** | SQL for methods, problems, existing pairs | In-memory from Claim objects |

**Reference advantages:**
- 12-field assessment dataclass (much richer)
- `adaptations_needed` and `estimated_improvement` are actionable
- `risk_factors` field
- Heuristic fallback includes modality matching (0.3–0.7 range)
- Task compatibility lookup table

**Our advantages:**
- Async-safe (extracted `_find_gaps_async`)
- Pipeline-integrated
- Real-LLM validated: BERT→SQuAD=0.95 vs BERT→ImageNet=0.10

---

### BATCH-134: StudyDesigner

| Aspect | Reference | Our Implementation |
|:-------|:----------|:-------------------|
| **Output** | `StudyDesign` with 11 structured components | `StudyDesign` with 9 fields |
| **Prompt** | Extremely detailed (~50 lines) requesting 11 components with specific sub-fields | ~25 lines requesting JSON with hypothesis, MVP, etc. |
| **Quantitative prediction** | Explicit field with example ("2-3x speedup on 16K-token sequences") | No dedicated field |
| **Experiment list** | Structured with purpose, setup, baselines, metrics, interpretation_if_success/failure, estimated_runtime | Single MVP experiment |
| **Publication strategy** | target_venues, contribution_type, likely_impact, potential_reviewer_concerns, preemptive_responses | Single string |
| **Action items** | Structured with type, priority, estimated_hours | Not included |
| **Template fallback** | Rich template with gap_type method+problem names | Rich template with gap method+problem names |

**Reference advantages:**
- Vastly more detailed prompt (forces LLM to produce richer output)
- Quantitative prediction requirement
- Experiment list with success/failure interpretation
- Action items with priority and time estimates
- Publication strategy with reviewer concerns + responses

**Our advantages:**
- External prompt file
- Pipeline-integrated
- Real-LLM validated: 370-char hypothesis mentioning "GoT"
- Template fallback still references actual method names

---

### BATCH-135: ConnectionAgent

| Aspect | Reference | Our Implementation |
|:-------|:----------|:-------------------|
| **Connection types** | 8 types: COMPLEMENTS, CONTRADICTS, EXTENDS, ALTERNATIVE_APPROACH, SHARES_INSIGHT, ENABLES, REPRODUCES, SYNTHESIS_OPPORTUNITY | 3 types: builds_on, contradicts, complements |
| **Data model** | `PaperConnection` (8 fields including potential_synthesis, llm_inferred) | `PaperConnection` (5 fields) |
| **Candidate finding** | Vector search for similar papers | Shared datasets between papers |
| **Explicit check** | Checks COMPARISON claims first | Checks COMPARISON claims + shared methods first |
| **Synthesis** | `potential_synthesis` field — what new capability would emerge | No synthesis field |
| **Vector service** | Dependency injection for vector similarity search | No vector dependency |

**Reference advantages:**
- 8 connection types (much richer taxonomy)
- `potential_synthesis` field for actionable insights
- Vector-based candidate finding (semantic similarity)
- More nuanced prompt with 8 specific relationship types

**Our advantages:**
- 3-path detection (COMPARISON → shared methods → LLM inference)
- No vector service dependency (works standalone)
- Event-loop-safe
- Real-LLM validated: BERT↔GPT identified as `complements`

---

### BATCH-136: Quality Validation

| Aspect | Reference | Our Implementation |
|:-------|:----------|:-------------------|
| **Test types** | Quality comparison tests (LLM vs shallow baseline) | Functional tests (does it work) + adversarial tests |
| **Metrics** | 5 aggregate metrics with 0.8 threshold | Per-module pass/fail |
| **E2E test** | Full comparison of LLM vs heuristic on same inputs | Real LLM quality spot-checks |
| **Mock sophistication** | Detailed per-case mock responses | Per-case mock responses |

**Reference advantages:**
- Structured quality metrics (wiki_verification_accuracy, contradiction_precision, etc.)
- Explicit LLM vs shallow comparison in every test
- 0.8 quality threshold with aggregate scoring
- This is a genuinely better testing approach

**Our advantages:**
- Real LLM validation (not mocks)
- Real E2E pipeline test with actual API calls
- asyncio.run bug found and fixed during testing

---

## Architecture Differences

| Aspect | Reference | Elephant Rock |
|:-------|:----------|:---------------|
| **Architecture** | Standalone agent classes | Pipeline-integrated modules |
| **DB dependency** | SQL queries via db_session | In-memory Claim objects |
| **Provider interface** | `llm.complete(prompt, response_format="json")` | `provider.complete(messages, temperature, max_tokens)` |
| **Data flow** | Module → DB → Module | Orchestrator → Stage → Module → Result |
| **Event loop** | Not addressed | Explicit async handling with loop detection |
| **Prompt storage** | Inline in code | External .md files |

---

## Actionable Recommendations

### HIGH PRIORITY (Significant quality improvement)

1. **Enrich WikiVerifier output model** — Add PARTIALLY_SUPPORTED and UNCLEAR states. Our binary supported/unsupported misses nuance. Add per-claim `ClaimVerification` objects with `confidence` and `source_evidence`.

2. **Expand source context from 3K → 10K chars** — Our 3K char truncation loses significant source context. The reference uses 15K. A middle ground of 10K would catch more fabrications.

3. **Add quality comparison tests** — The reference's "LLM vs shallow baseline" test pattern is genuinely better than our functional tests. We should add `test_quality_vs_shallow` for each module.

4. **Add `potential_synthesis` to ConnectionAgent** — This is the single most valuable field the reference proposes. When two papers are connected, suggesting what new capability would emerge from combining them is highly actionable.

### MEDIUM PRIORITY (Nice to have)

5. **Enrich MethodProblemDetector assessment** — Add `adaptations_needed`, `estimated_improvement`, and `risk_factors` fields. These make the output actionable rather than just scored.

6. **Improve ContradictionDetector fallback heuristic** — Our heuristic returns uniform 0.5. The reference uses modality matching + task compatibility to produce 0.3–0.7 range.

7. **Add reconciliation checking to ContradictionDetector** — Check if any paper already reconciles contradictory findings before flagging them.

### LOW PRIORITY (Marginal improvement)

8. **Expand StudyDesigner prompt** — Add quantitative_prediction, experiment_list with interpretation_if_success/failure, action_items with priority. The reference prompt is 2x longer and produces richer output.

9. **Expand ConnectionType to 8 types** — Our 3 types (builds_on, contradicts, complements) cover the main cases. The reference's 8 types are richer but may produce lower-accuracy classifications.

10. **Add `_verification` metadata to wiki entries** — Timestamp, verifier version, needs_human_review flag. Useful for audit trails.

---

## What Our Implementation Does Better

1. **External prompt files** — Easier to modify without touching code. Reference embeds all prompts inline.
2. **Pipeline integration** — Works with the existing orchestrator, stages, and data models. Reference assumes standalone use.
3. **Event loop safety** — Our `asyncio.run()` bug fix (loop detection pattern) is essential for real deployment. Reference doesn't address this.
4. **Real-LLM validation** — We tested with actual API calls against real data. Reference uses sophisticated mocks.
5. **Immutable inputs** — HB-03 (deep copy) prevents data corruption. Reference mutates wiki entries.
6. **Closed-book policy** — Explicitly enforced in prompts. Reference doesn't mention citation integrity.
7. **3-path connection detection** — COMPARISON → shared methods → LLM inference gives better recall than reference's 2-path approach.

---

## Conclusion

The reference is a **well-designed specification** for the same modules, produced independently. It focuses on **richness of output** (12-field assessments, 8 connection types, 5 verification states) while our implementation focuses on **pipeline integration and robustness** (event loop safety, external prompts, closed-book integrity).

The highest-value improvements to adopt:
1. Quality comparison tests (LLM vs shallow baseline)
2. `potential_synthesis` field on connections
3. Enriched assessment dataclasses (adaptations, risks, estimated improvement)
4. Wider source context (3K → 10K chars)

These improvements can be implemented as Phase 9.2 batches without changing the core architecture.
