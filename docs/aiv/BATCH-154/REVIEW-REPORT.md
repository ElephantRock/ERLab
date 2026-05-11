# REVIEW REPORT — BATCH-154

**Reviewer:** Craft Agent (AIV Framework v5.3)  
**Review Cycle:** 1  
**Blueprint Version:** 1.0  
**Date:** 2026-05-11T03:33+03:00  
**Blueprint File:** `docs/aiv/BATCH-154/BLUEPRINT.md`

---

## CHK-00 — Cycle Mode

**PASS**

Blueprint declares `Cycle Mode: STANDARD`. Task count is 3, all sequential, each with critical/high priority. Execution SLAs are stated (60 min/task, 30 min review, 15 min sign-off). No stream-blend, no hotfix mode needed. Cycle mode is appropriate for the scope.

---

## CHK-01 — Batch Goal

**PASS**

The goal is specific, bounded, and testable: create a post-processing audit stage that verifies citations and quantitative claims across three axes (existence, context, quantitative accuracy). The three axes map cleanly to distinct code paths in the proposed `CitationClaimAuditor`. No ambiguity in what "done" looks like.

---

## CHK-02 — Scope Statement

**PASS**

**MUST-do** is precise:
- New class `CitationClaimAuditor` with methods enumerated (a)–(e).
- New stage `CitationAuditStage` with behaviors enumerated (a)–(e).
- Registration in `_STAGE_ORDER` and extension of `ReferenceVerifier`.

**MUST-NOT-do** is well-drawn:
- No modification to `ClaimExtractor` (verified — extractor is a separate LLM-path module, no overlap).
- No API endpoint changes.
- No new DB tables/migrations (storage via `proposal.metadata` JSON — consistent with existing pattern).
- No network access.
- No pipeline blocking on failure.

Boundary is clean and respects the AIV principle of minimal blast radius.

---

## CHK-03 — Hard Boundaries

**PASS**

| Boundary | Verifiable? | Notes |
|:---------|:-----------:|:------|
| HB-01: 2,536 pre-existing tests pass | ✓ | Test baseline confirmed in STATE.md. Lint command provided. |
| HB-02: Audit MUST NOT block on LLM failure | ✓ | TEST-154-01-04 falsifies this. |
| HB-03: `[SOURCE-X]` index validated against source count | ✓ | TEST-154-01-02 falsifies this. |
| HB-04: Trust score clamped [0.0, 1.0] | ✓ | TEST-154-01-03 falsifies this. |
| HB-05: 60-second per-proposal timeout | ✓ | Described in TASK-01 item (j). |

All boundaries are falsifiable with concrete test cases.

---

## CHK-04 — Data Models / Schema

**PASS** with note

**CitationAuditItem** — 8 fields, all typed. `ref_index: int`, `ref_exists: bool`, `claim_text: str`, `context_verified: bool`, `context_justification: str`, `quantitative_claims: list[dict]`, `quantitative_verified: bool`, `trust_contribution: float`. Clean.

**CitationAuditReport** — 10 fields. `proposal_id: int`, `total_citations: int`, `verified_citations: int`, `fabricated_citations: int`, `context_mismatches: int`, `quantitative_errors: int`, `trust_score: float`, `items: list[CitationAuditItem]`, `model_used: str`, `status: str`.

Storage path: `proposal.metadata["citation_audit"]` → consistent with how `adversarial_review`, `full_paper`, and `deepened` are stored in existing stages.

> **Note (non-blocking):** `CitationAuditReport.to_dict()` is referenced in the storage spec but no method is defined in the data model section. Implementer must add this — it's obvious but should be explicit. Also, `quantitative_claims: list[dict]` is weakly typed for a verification system; a `QuantitativeClaim` dataclass would improve type safety. Neither blocks acceptance.

---

## CHK-05 — Tasks

**PASS**

| Task | Priority | Dependencies | Files in Scope | Tests |
|:-----|:---------|:-------------|:---------------|:------|
| TASK-01 | Critical | None | 2 NEW files | 6 |
| TASK-02 | Critical | TASK-01 | 3 MODIFY files | 5 |
| TASK-03 | High | TASK-02 | 2 MODIFY files | 3 |
| **Total** | | | **7 files** | **14** |

Sequential dependency chain is correct: auditor must exist before stage can use it; stage must exist before presets can reference it. No circular dependencies.

---

## CHK-06 — Tests

**PASS** with flags (see CHK-07)

Each test has:
- Test ID following convention ✓
- Type (all unit) ✓
- Behavior verified ✓
- Failure mode ✓
- Falsified-by column ✓
- Pass criteria ✓

Expected delta: +14 tests (2,536 → 2,550). Matches TASK-01 (6) + TASK-02 (5) + TASK-03 (3).

---

## CHK-07 — Consistency & Codebase Verification

### 7a. `_STAGE_ORDER` — Current State Verified

```python
_STAGE_ORDER = [
    "literature_search",      # 0
    "ingestion",              # 1
    "gap_analysis",           # 2
    "idea_generation",        # 3
    "novelty_checking",       # 4
    "feasibility_scoring",    # 5
    "mechanical_metrics",     # 6
    "proposal_synthesis",     # 7
    "adversarial_review",     # 8
    "paper_synthesis",        # 9
    "proposal_deepening",     # 10
    "export",                 # 11
]
```

**Confirmed: 12 entries** (matches STATE.md DEC-004). Blueprint correctly states 12 → 13 with `citation_audit` inserted after `paper_synthesis` (index 9) and before `proposal_deepening` (index 10).

**PASS**

---

### 7b. `_get_metadata` / `_set_metadata` — Pattern Verified

Both `PaperSynthesisStage` and `AdversarialReviewStage` implement identical `_get_metadata`/`_set_metadata` static methods that handle JSON-string or dict storage. The new `CitationAuditStage` must replicate this pattern.

> **FLAG-01 (Low):** `_get_metadata`/`_set_metadata` is duplicated across 3 stages (including the new one). Consider extracting to a shared utility on `PipelineStage` base class or a mixin. Not blocking — the blueprint is consistent with existing practice — but this is accumulating tech debt.

---

### 7c. `ReferenceVerifier` — Current State Verified

Current patterns handled:
- `Author et al., YEAR` via `_CITATION_PATTERN`
- `[N]` numbered references via `_NUMBERED_REF_PATTERN`

**Not handled:** `[SOURCE-X]` pattern (used in closed-book citation policy from BATCH-111). Blueprint correctly identifies this gap and TASK-03 extends it. The extension is additive (new regex, new method) — no existing logic is disrupted.

**PASS**

---

### 7d. `ClaimExtractor` / `Claim` Models — Verified

- `ClaimExtractor` is LLM-based structured extraction from paper text — completely separate concern from `CitationClaimAuditor`.
- `Claim` dataclass has 22+ fields with `source_paper_id` as required (HB-02).
- `ClaimType` enum: METHOD, RESULT, LIMITATION, FUTURE_WORK, COMPARISON.
- Blueprint correctly states MUST NOT modify these.

**PASS**

---

### 7e. Strategy Presets — Current State Verified

Current 4 presets use `_all_stages_enabled(**overrides)` helper that lists exactly 12 stage names. After BATCH-154, this function must be updated to include `"citation_audit"` (13 entries).

**FLAG-02 (Medium): Strategy gating mechanism is underspecified.**

The blueprint says:
- TASK-02: "Only run when strategy has `citation_audit` enabled"
- TASK-03: "deep_research: citation_audit=true", "fast_scan: citation_audit=false"

But the existing mechanism uses `StageConfig.enabled` (boolean), not a params flag. The orchestrator gates stages via:
```python
strategy_stage = self._strategy_config.stages.get(stage.name)
if strategy_stage is not None and not strategy_stage.enabled:
    continue
```

**Recommendation:** Implement as `StageConfig()` (default enabled=True) for deep_research/academic_proposal, and `StageConfig(enabled=False)` for fast_scan/literature_review. Do NOT use a `params={"citation_audit": True}` flag — that adds an indirection layer that's unnecessary for a full stage. The existing orchestrator gating handles this correctly.

---

### 7f. `get_thinking_provider()` — Verified

Referenced in Authority Rule A-01. Confirmed it exists in `backend/providers/provider_factory.py` and is already used by `AdversarialReviewStage` and the model selector. Blueprint correctly routes audit to the thinking provider (local LM Studio), not the generation provider.

**PASS**

---

### 7g. Missing Test for HB-05 (Timeout)

**FLAG-03 (Medium): No test verifies the 60-second timeout behavior (HB-05).**

HB-05 states: "Audit must complete within 60 seconds per proposal. If LLM timeout occurs, return partial results with timeout flag."

TEST-154-01-04 tests LLM *failure* (exception), not *timeout*. These are different failure modes:
- Failure → `status="skipped"` (no partial results)
- Timeout → `status="partial"` (partial results with items collected so far)

**Recommendation:** Add TEST-154-01-07:
> | TEST-154-01-07 | unit | Timeout returns partial results | Audit hangs forever | Mock LLM with 61s delay | Returns report with status="partial", items collected before timeout |

This directly falsifies HB-05.

---

### 7h. STATE.md DEC-003 is Stale (Informational)

DEC-003 lists "10 stage names" but DEC-004 (added in BATCH-153) says 12 entries. The stage name list in DEC-003 was never updated after adversarial_review and paper_synthesis were added.

> **Not a flag on this blueprint.** BATCH-154 should update DEC-003 when it adds citation_audit (making it 13). The STATE.md update is already covered by BAC-06.

---

### 7i. TASK-03 Scope Mix

**FLAG-04 (Low): TASK-03 bundles two unrelated concerns.**

TASK-03 does both:
- (a–d) Wire strategy presets for citation_audit
- (e) Extend `ReferenceVerifier` with `[SOURCE-X]` pattern support

Preset wiring is a configuration task. ReferenceVerifier extension is a code logic task. These have different risk profiles and different files. Splitting would improve isolation and make rollback cleaner.

**Recommendation:** If time permits, split TASK-03 into TASK-03a (presets) and TASK-03b (ReferenceVerifier extension). Not blocking — both are low-risk modifications.

---

## Flag Summary Table

| Flag | Severity | Category | Description | Recommendation |
|:-----|:---------|:---------|:------------|:---------------|
| FLAG-01 | Low | Tech Debt | `_get_metadata`/`_set_metadata` duplicated across stages (will be 4 after this batch) | Extract to `PipelineStage` mixin in a future batch. Not blocking. |
| FLAG-02 | Medium | Ambiguity | Strategy gating uses `StageConfig.enabled` but blueprint says `citation_audit: true/false` — unclear if this is `enabled` or `params` flag | Clarify in implementation: use `StageConfig()` / `StageConfig(enabled=False)`. Do NOT use params flag. |
| FLAG-03 | Medium | Test Gap | No test for HB-05 timeout (60s per proposal). TEST-154-01-04 covers failure, not timeout. | Add TEST-154-01-07 for partial-results-on-timeout. |
| FLAG-04 | Low | Scope | TASK-03 mixes preset wiring with ReferenceVerifier extension | Consider splitting. Not blocking. |

---

## Additional Observations (Non-Flag)

1. **Lint command is solid.** Backend lint (`from backend.config import get_settings`) catches import breaks. Test command includes `-p no:asyncio` to avoid the GOTCHA-001 trio-mode failures.

2. **Dependency map is accurate.** BATCH-153 (paper_synthesis) is confirmed complete in STATE.md. BATCH-111 (closed-book citation) established the `[SOURCE-X]` format. BATCH-112 created the ReferenceVerifier.

3. **Authority rules are sound.** A-01 (thinking provider for analysis), A-02 (proposal + full paper + source papers as inputs), A-03 (only [SOURCE-X] format, not Author-style), A-04 (stage name and position) — all consistent with existing patterns.

4. **The `CitationAuditReport.status` enum values ("complete", "partial", "skipped") align cleanly with the three HB-02/HB-05 failure modes.**

5. **Lead Response section is properly formatted** with fields for reviewer report ID, cycle number, decision checkboxes, and flag tracking.

---

## Verdict

### **ACCEPT WITH MODIFICATIONS**

The blueprint is well-structured, internally consistent, and accurately references the codebase. The scope is appropriate for a STANDARD cycle. The four flags are:

- **FLAG-02 and FLAG-03 (Medium):** Must be addressed before or during implementation. FLAG-02 requires clarifying the gating mechanism (use `StageConfig.enabled`). FLAG-03 requires adding a timeout test.
- **FLAG-01 and FLAG-04 (Low):** Should be noted for future cleanup but do not block this batch.

**Conditions for Accept:**
1. Clarify strategy gating: use `StageConfig()` / `StageConfig(enabled=False)`, not a params flag.
2. Add TEST-154-01-07 to cover HB-05 timeout → partial results path.
3. Update `_all_stages_enabled()` stage_names list to include `"citation_audit"` (13 entries).
4. Add `to_dict()` method specification to `CitationAuditReport` data model section.

═══════════════════════════════════════════════════════════
