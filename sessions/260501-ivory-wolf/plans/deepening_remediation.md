# Deepening Remediation Plan — Phase 9 Quality Hardening

**Lead Programmer:** ivory-wolf  
**Date:** 2026-05-09  
**Problem:** 4 of 6 Phase 9 modules use heuristics/stubs instead of real LLM reasoning  
**Root Cause:** Lead Override shortcut — no independent Reviewer caught the stubs  

---

## Diagnosis

| Module | Current | What It Should Be |
|:-------|:--------|:------------------|
| **WikiVerifier** | Keyword overlap (>=40% word match) | LLM judges if each claim is supported by source text |
| **ContradictionDetector._verify** | Numeric >10% heuristic | LLM determines if two results genuinely contradict vs. different experimental conditions |
| **MethodProblemDetector._score_gap** | Returns hardcoded 0.5 | LLM assesses applicability of method to dataset + estimates potential improvement |
| **StudyDesigner** | String templates with f-strings | LLM generates hypothesis, mechanistic rationale, MVP pseudocode grounded in the actual idea text |
| **ConnectionAgent** | Only COMPARISON claims + shared method names | LLM infers implicit connections from method/result overlap + identifies non-obvious relationships |

---

## Remediation Batches

### BATCH-131: LLM-Grounded WikiVerifier (STANDARD)
Replace keyword overlap with LLM-based claim verification.
- Provider calls `complete()` with each claim + source text
- LLM returns: supported (bool), reasoning (str)
- Falls back to keyword overlap if LLM fails
- **Quality test**: Feed real wiki with intentionally wrong claim → must flag it

### BATCH-132: LLM-Grounded Contradiction Verification (STANDARD)
Replace numeric heuristic with LLM verification.
- Provider calls `complete()` with both claims + context
- LLM determines: genuine contradiction, different conditions, or incomparable
- **Quality test**: Feed 28.4 BLEU EN→DE vs 28.4 BLEU FR→EN → must say "not contradictory" (different direction)

### BATCH-133: LLM-Grounded Method-Problem Scoring (STANDARD)
Replace hardcoded 0.5 with LLM applicability assessment.
- Provider calls `complete()` or `structured_output()` with method name + dataset
- Returns: applicability_score (0-1), reasoning, estimated_improvement
- **Quality test**: BERT on ImageNet should score lower than BERT on SQuAD

### BATCH-134: LLM-Grounded StudyDesigner (STANDARD)
Replace string templates with LLM generation.
- Provider generates hypothesis, mechanistic rationale, MVP pseudocode from actual idea text
- Falls back to templates if LLM fails
- **Quality test**: Generated hypothesis references actual method name and problem domain

### BATCH-135: LLM-Grounded Connection Agent (STANDARD)
Add LLM-based connection inference beyond COMPARISON claims.
- Provider assesses pairs of METHOD/RESULT claims for implicit relationships
- Returns: connection_type, confidence, evidence
- **Quality test**: BERT (bidirectional pre-training) ↔ GPT (autoregressive) → "complements" detected

### BATCH-136: Quality Validation (SIMPLIFIED)
Run real E2E with all deepened modules. Verify quality metrics improved vs. shallow baseline.

---

## Test Standard Change

Old tests verified: "doesn't crash, returns right type"  
New tests verify: "LLM output is semantically correct"

Every deepened module gets:
1. **Happy path test** — real LLM call produces quality output
2. **Fallback test** — works without LLM (degrades to heuristic)
3. **Quality test** — intentional wrong input is caught/rejected

---

## Expected Outcome

| Module | Before | After |
|:-------|:-------|:------|
| WikiVerifier quality scoring | Keyword 0-1, noisy | LLM-judged, calibrated |
| Contradiction verification | Numeric heuristic only | LLM context-aware judgment |
| Method-problem scoring | All 0.5 | 0.1-0.9 range, differentiated |
| Study design quality | Template strings | Grounded in actual idea content |
| Connection depth | COMPARISON claims only | Inferred from method/result overlap |
