# BATCH-114 BLUEPRINT — ProposalDeepener Pipeline Stage

**Batch ID:** BATCH-114  
**Blueprint Version:** 1.0  
**Cycle Mode:** STANDARD  
**Lead Programmer:** ivory-wolf  
**Date Issued:** 2026-05-07  

## BATCH GOAL

Create a ProposalDeepenerStage that runs after synthesis and enriches
each proposal with concrete architecture, toy example, failure modes,
and measurable success criteria.

## HARD BOUNDARIES

- **HB-01:** Deepening failure MUST NOT halt the pipeline
- **HB-02:** Deepening MUST NOT overwrite the original proposal text

## TEST BASELINE

| Metric | Value |
|:-------|:------|
| Baseline | 2,260 |
| Expected delta | +7 |
| Expected total | 2,267 |

## TASK LIST

### TASK-01: Create ProposalDeepenerStage

**Priority:** Critical  
**Files in scope:**
- `backend/pipeline/stages.py` (MODIFY)
- `backend/pipeline/orchestrator.py` (MODIFY — _STAGE_ORDER)

| Test ID | Type | Behavior Verified | Failure Mode | Falsified By | Pass Criteria |
|:--------|:-----|:------------------|:-------------|:-------------|:--------------|
| TEST-114-01-01 | unit | ProposalDeepenerStage class exists | ImportError | Remove class | import succeeds |
| TEST-114-01-02 | unit | Stage runs without crashing (HB-01) | Exception blocks pipeline | Raise in deepener | Pipeline continues |
| TEST-114-01-03 | unit | Template mode produces all 4 sections | Missing sections | Remove template | all 4 fields non-empty |
| TEST-114-01-04 | unit | Deepened content stored in metadata | Data lost | Skip write | "deepened" in metadata |
| TEST-114-01-05 | unit | Original proposal text unchanged (HB-02) | Content overwritten | Compare before/after | before == after |
| TEST-114-01-06 | unit | _STAGE_ORDER includes deepening | Stage not in order | Remove from list | "proposal_deepening" in _STAGE_ORDER |
| TEST-114-01-07 | unit | Stage positioned after synthesis | Wrong order | Move before | index > proposal_synthesis |

## BAC

- BAC-01: ProposalDeepenerStage wired into _STAGE_ORDER
- BAC-02: All 7 tests pass
- BAC-03: CHANGELOG.md updated
- BAC-04: Documents archived under /docs/aiv/BATCH-114/
