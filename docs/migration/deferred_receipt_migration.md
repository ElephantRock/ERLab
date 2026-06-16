# Deferred Receipt Migration — 9 Remaining Stages

**Created**: 2026-06-17
**Status**: Pattern established, mechanical migration deferred

## Completed (4 core services)

| Service | Method | Receipt Source |
|---------|--------|---------------|
| GapAnalyzer | `analyze()` | `provider.default_model` |
| FeasibilityScorer | `score_feasibility()` | `provider.default_model` |
| ProposalSynthesizer | `synthesize()` | `provider.default_model` |
| AgentOrchestrator | `run()` | `provider.default_model` |

## Remaining (9 stages)

Each follows the same pattern:
1. Add `receipts: list | None = None` kwarg to the service method
2. Before the LLM call, append `build_receipt_from_provider(llm)` to receipts
3. In stages.py, pass `receipts=ctx.receipts` from the stage's execute method

| Stage | Service | Method | Priority |
|-------|---------|--------|----------|
| NoveltyCheckingStage | NoveltyChecker | `check_novelty()` | High (core quality) |
| AdversarialReviewStage | (inline LLM) | `_review_proposal()` | Medium |
| PaperSynthesisStage | PaperSynthesizer | `synthesize()` | Medium |
| ProposalDeepeningStage | (inline LLM) | `_deepen()` | Low |
| CitationAuditStage | CitationClaimAuditor | `audit()` | Medium |
| EvaluationStage | (inline LLM) | `_evaluate()` | Low |
| GapReflectionStage | (inline LLM) | `_reflect()` | Low |
| IdeaReflectionStage | (inline LLM) | `_reflect()` | Low |
| TreeSearchStage | (inline LLM) | various | Low |

## Non-Model Stages (no receipt required)

| Stage | Reason |
|-------|--------|
| LiteratureSearchStage | API search, no LLM |
| MechanicalMetricsStage | Computed metrics |
| ExportStage | File writing |

These are declared in `NON_MODEL_STAGES` frozenset in `stages.py`.
