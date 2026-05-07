# BATCH-113 BLUEPRINT — Citation Grounding in Gap Analysis

**Batch ID:** BATCH-113  
**Blueprint Version:** 1.0  
**Cycle Mode:** STANDARD  
**Lead Programmer:** ivory-wolf  
**Date Issued:** 2026-05-07  

## BATCH GOAL

Add citation grounding to the gap analysis prompt so gaps reference
actual papers from the corpus instead of inventing references.

## HARD BOUNDARIES

- **HB-01:** Gap analysis must still produce gaps even if no papers are provided
- **HB-02:** Prompt changes must not reduce gap quality (still 5-7 per run)

## TEST BASELINE

| Metric | Value |
|:-------|:------|
| Baseline | 2,252 |
| Expected delta | +8 |
| Expected total | 2,260 |

## TASK LIST

### TASK-01: Harden Gap Analysis Prompt with Citation Integrity

**Priority:** High  
**Files in scope:** `backend/pipeline/gap_analysis/gap_analyzer.py`

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-113-01-01 | unit | Prompt contains citation integrity instruction | Missing | Remove text | "CITATION INTEGRITY" in prompt |
| TEST-113-01-02 | unit | Paper summaries include author names | Authors missing | Remove author formatting | Author name in formatted output |
| TEST-113-01-03 | unit | Prompt works with empty papers (HB-01) | IndexError | Pass [] | No exception |
| TEST-113-01-04 | unit | Prompt instructs not to invent citations | Instruction missing | Remove text | "only reference" or "do not invent" in prompt |
| TEST-113-01-05 | unit | Paper summaries include year | Year missing | Remove year | Year present in formatted output |
| TEST-113-01-06 | unit | GapAnalyzer initializes with provider | TypeError | Pass None | Object created |
| TEST-113-01-07 | unit | Paper summaries respect 30-paper limit | >30 formatted | Pass 50 papers | Count ≤ 30 |
| TEST-113-01-08 | unit | Gap types are valid | Invalid types | Check values | All types in allowed set |

## BATCH-LEVEL ACCEPTANCE CRITERIA

- BAC-01: Gap analysis prompt includes citation integrity instructions
- BAC-02: All 8 tests pass
- BAC-03: CHANGELOG.md updated
- BAC-04: All documents archived under /docs/aiv/BATCH-113/

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

Reviewer Report ID:       REVIEW-BATCH-113-2026-05-07
Review Cycle:             1
Lead Decision:            [x] ACCEPT   [ ] ACCEPT WITH MODIFICATIONS   [ ] REJECT

0 flags. Reviewer confirmed all CHK items PASS. Proceed to execution.

Blueprint Version after response: 1.0
Lead Sign:                ivory-wolf — 2026-05-07
