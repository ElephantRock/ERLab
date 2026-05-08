# Phase 9.1 Deepening Remediation — Batch Blueprint Sequence

**Lead Programmer:** ivory-wolf  
**Framework:** AIV v5.3  
**Date:** 2026-05-09  
**Preceding Phase:** Phase 9 (B121–B130) — CLOSED  
**Test Baseline:** 2,361  
**Problem:** 5 of 6 Phase 9 modules use heuristics/stubs instead of real LLM reasoning. Lead Override bypassed Reviewer scrutiny, allowing stubs through.  
**Root Cause:** Sessions queued as `todo` for 5+ minutes; Lead implemented directly (§5.3 Override) without independent Review catching the shortcuts.

---

## Strategic Context

Phase 9 built the **structured knowledge layer** (claims, wiki, curation, contradictions, method-problem gaps, study design, connections). The architecture is correct — ClaimExtractor produces real LLM-grounded claims. But the **downstream reasoning modules** that consume those claims all use shallow heuristics:

| Module | Current Behavior | Defect |
|:-------|:-----------------|:-------|
| WikiVerifier | Keyword overlap ≥40% | Flags nothing that shares 2+ words with source |
| ContradictionDetector._verify | Numeric >10% heuristic | Misses non-numeric contradictions; can't explain WHY |
| MethodProblemDetector._score_gap | Returns hardcoded 0.5 | Every gap looks equally promising |
| StudyDesigner | F-string template strings | Hypothesis doesn't reference actual method/problem |
| ConnectionAgent | COMPARISON claims + shared methods only | Misses implicit conceptual relationships |

**The ClaimExtractor is already LLM-grounded.** The fix is to give the same LLM capability to the modules that consume its output.

---

## Batch Sequence Overview

| Batch | Cycle | Goal | Strategic Bet | Tests |
|:------|:------|:-----|:-------------|:------|
| **B131** | STANDARD | LLM-Grounded WikiVerifier | LLM can judge claim support more accurately than keyword overlap | +8 |
| **B132** | STANDARD | LLM-Grounded Contradiction Verification | LLM can distinguish genuine contradictions from experimental variation | +7 |
| **B133** | STANDARD | LLM-Grounded Method-Problem Scoring | LLM can assess method→dataset applicability with differentiated scores | +7 |
| **B134** | STANDARD | LLM-Grounded StudyDesigner | LLM produces hypothesis+MVP grounded in actual idea text | +7 |
| **B135** | STANDARD | LLM-Grounded Connection Agent | LLM infers implicit relationships beyond COMPARISON claims | +6 |
| **B136** | SIMPLIFIED | Deepening Validation | Real E2E with all deepened modules, quality comparison vs. shallow baseline | +0 |

**Totals:** 6 batches, ~35 new tests, ~2,396 expected total

---

## Risk Hypotheses Per Batch

| Batch | Hypothesis | Risk if Wrong | Mitigation |
|:------|:-----------|:-------------|:-----------|
| B131 | LLM can judge claim support with <5% false positive rate | LLM hallucinates support | Fallback to keyword overlap; threshold tuning |
| B132 | LLM can distinguish contradictions from variations | All pairs flagged or none | Structured output with explicit reasoning field |
| B133 | LLM applicability scores differentiate meaningfully | All scores cluster near 0.5 | Structured output with score + reasoning + improvement estimate |
| B134 | LLM generates hypotheses referencing actual method/problem | Generic hypotheses | Prompt includes full idea text; test asserts method name appears |
| B135 | LLM finds non-obvious connections | Only trivial connections | Quality test with known deep connection pair |
| B136 | All deepened modules improve over shallow baseline | Regressed quality | Keep fallback paths; A/B comparison |

---

## Decision Gates

| After Batch | Decision | Go/No-Go Criteria |
|:-----------|:---------|:------------------|
| B131 | WikiVerifier quality adequate? | LLM verification flags ≥1 intentionally wrong claim in test; false positive rate <20% |
| B133 | Method-problem scores differentiated? | Score range spans ≥0.3 (not all 0.5); BERT+SQuAD > BERT+ImageNet |
| B136 | Deepening improved quality? | All 5 deepened modules pass real-LLM quality tests; no regressions in existing 69 tests |

---

## Test Standard Change

**Old (Phase 9):** Tests verify structure — "doesn't crash, returns right type"  
**New (Phase 9.1):** Tests verify semantic quality — "LLM output is correct for the input"

Every deepened module gets three test categories:
1. **LLM Quality Test** — Real or semi-real LLM call, assert semantic correctness
2. **Fallback Test** — Works without LLM provider (degrades to heuristic gracefully)
3. **Adversarial Test** — Intentionally wrong input is caught/rejected
