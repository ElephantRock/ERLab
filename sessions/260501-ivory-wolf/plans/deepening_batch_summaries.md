# Phase 9.1 Remaining Batch Summaries — B132 through B136

## BATCH-132: LLM-Grounded Contradiction Verification
**Cycle:** STANDARD | **Tests:** +7 | **Files:** 1 mod + 1 prompt

**Goal:** Replace the numeric >10% heuristic in ContradictionDetector._verify_contradiction() with LLM-based context analysis. The LLM receives both claims + their paper context and determines: genuine contradiction, different experimental conditions (e.g., EN→DE vs FR→EN), or incomparable. Returns structured reasoning.

**Strategic Bet:** LLM can distinguish "28.4 BLEU on WMT EN→DE" from "28.4 BLEU on WMT FR→EN" as non-contradictory (different language direction), which the current heuristic cannot.

**Key Decisions:**
- Provider calls `complete()` with both claims + source contexts
- Returns: {"is_genuine": bool, "category": "contradiction|different_conditions|incomparable", "reasoning": str}
- Falls back to numeric heuristic on LLM failure
- Prompt at `claims/contradiction/prompts/verification.md`

**Quality Test:** Feed 28.4 BLEU EN→DE vs 28.4 BLEU FR→EN → must say "different_conditions" not "contradiction"

---

## BATCH-133: LLM-Grounded Method-Problem Scoring
**Cycle:** STANDARD | **Tests:** +7 | **Files:** 1 mod + 1 prompt

**Goal:** Replace `return 0.5` in MethodProblemDetector._score_gap() with LLM-based applicability assessment. LLM receives method name + method description + dataset name, returns: applicability_score (0.0-1.0), reasoning, estimated_improvement (str).

**Strategic Bet:** LLM can meaningfully differentiate — BERT on SQuAD should score higher than BERT on ImageNet.

**Key Decisions:**
- Provider calls `complete()` with method + dataset context
- Returns: {"applicability_score": float, "reasoning": str, "estimated_improvement": str}
- Falls back to 0.5 on LLM failure
- Prompt at `claims/prompts/applicability_scoring.md`

**Quality Test:** BERT+SQuAD applicability > BERT+ImageNet applicability

---

## BATCH-134: LLM-Grounded StudyDesigner
**Cycle:** STANDARD | **Tests:** +7 | **Files:** 1 mod + 1 prompt

**Goal:** Replace f-string template generation in StudyDesigner with LLM-grounded hypothesis, mechanistic rationale, and MVP pseudocode. The LLM receives the actual idea text (title, problem, method) and generates a study design referencing the specific method and problem domain.

**Strategic Bet:** LLM can produce a hypothesis like "Applying Graph-of-Thought reasoning to multi-step mathematical word problems will reduce error rates by enabling explicit backtracking through reasoning paths" — not a generic template.

**Key Decisions:**
- design_from_idea() uses LLM when provider available
- Falls back to template generation on LLM failure
- MVP pseudocode references actual method name and problem type
- Prompt at `claims/prompts/study_design.md`

**Quality Test:** Generated hypothesis contains the actual method name AND problem domain name from the input

---

## BATCH-135: LLM-Grounded Connection Agent
**Cycle:** STANDARD | **Tests:** +6 | **Files:** 1 mod + 1 prompt

**Goal:** Add LLM-based connection inference beyond COMPARISON claims and shared method names. For each pair of papers with overlapping RESULT claims (same dataset), the LLM assesses whether there's an implicit conceptual relationship. Returns: connection_type, confidence, evidence.

**Strategic Bet:** LLM can identify that BERT (bidirectional pre-training) and GPT (autoregressive) are complementary approaches to language modeling, even without an explicit COMPARISON claim.

**Key Decisions:**
- For each paper pair sharing a dataset, call LLM to classify relationship
- Returns: {"connection_type": "builds_on|contradicts|complements", "confidence": float, "evidence": str}
- Keep existing COMPARISON + shared-method paths
- Prompt at `claims/prompts/connection_inference.md`

**Quality Test:** Given BERT+GPT-3 papers with shared datasets, LLM infers "complements" relationship

---

## BATCH-136: Deepening Validation (Phase 9.1 Close)
**Cycle:** SIMPLIFIED | **Tests:** +0 | **Files:** 0 new

**Goal:** Run real E2E with all 5 deepened modules. Compare quality metrics vs. shallow baseline from Phase 9. Update STATE.md. Write quality comparison report.

**Strategic Bet:** The deepened modules produce measurably better output than the heuristic versions.

**Key Decisions:**
- SIMPLIFIED cycle: 1 Task (validation only)
- Quality comparison: deepened vs. shallow on same 3 paper abstracts
- STATE.md updated with Phase 9.1 module map
- All 35 new tests + 69 existing Phase 9 tests must pass
