# Phase 8 Master Roadmap — Pipeline Quality Hardening

**Lead:** ivory-wolf | **Framework:** AIV v5.3 | **Test Baseline:** 2,244
**Created:** 2026-05-07 | **Batches:** BATCH-112 through BATCH-121 (10 batches)

---

## Motivation

The research paper on GoT × Neuro-Symbolic Reasoning was reviewed by an expert. Three critical pipeline quality weaknesses were exposed:

1. **Hallucinated references** — Pipeline generates proposals with fabricated citations
2. **Shallow proposals** — Proposals lack concrete architecture, toy examples, failure modes
3. **No quality metrics** — No precision/recall on gap detection, no pipeline self-evaluation

BATCH-111 created the three verification modules (ReferenceVerifier, ProposalDeepener, PipelineEvaluator) and hardened the synthesis prompt. Phase 8 wires them into the pipeline as actual stages, adds cross-run deduplication, and validates with a real end-to-end run.

---

## Phase Structure

| Sub-Phase | Batches | Focus | Tests |
|:----------|:--------|:------|:------|
| **8A — Reference Integrity** | B112–B113 | Wire verifier into pipeline + add citation grounding to gap analysis | +16 |
| **8B — Proposal Depth** | B114–B115 | Wire deepener as stage + add evaluation plan generator | +14 |
| **8C — Quality Measurement** | B116–B117 | Wire evaluator + add gold-standard gap lists + cross-run dedup | +14 |
| **8D — Validation** | B118–B120 | Real pipeline run with all quality gates + paper re-generation + final verification | +8 |

**Total:** 10 batches, ~52 new tests, expected baseline at close: 2,296

---

## BATCH-112: ReferenceVerifier Pipeline Integration

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID:                 BATCH-112
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Wire the ReferenceVerifier into the orchestrator so it runs automatically
after proposal synthesis. Unverifiable citations are stripped and logged.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add a post-synthesis verification step in the orchestrator
  - Pass the corpus papers + proposal text to ReferenceVerifier
  - Strip unverifiable citations from proposal sections
  - Log verification results (trust score, hallucinated count)

What the code MUST NOT do:
  - Must NOT block pipeline completion if verification fails (HB-01)
  - Must NOT modify the gap analysis or idea generation stages
  - Must NOT change the proposal synthesizer's prompt (already done in B111)

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Reference verification failure MUST NOT crash or halt the pipeline.
         It MUST log warnings and continue with stripped citations.
  HB-02: The verification step MUST run AFTER synthesis, never before.

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,244
  Expected delta:                  +8
  Expected total at Batch close:   2,252

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Wire ReferenceVerifier into Orchestrator Post-Synthesis
  Priority:          Critical
  Description:       Add a _verify_references() method to PipelineOrchestrator
                     that runs after proposal_synthesis. It calls
                     ReferenceVerifier.verify() with the proposal text and
                     corpus papers. If trust_score < 0.7, it strips citations
                     via strip_unverified_citations(). Results are logged.
  Files in scope:
    - backend/pipeline/orchestrator.py (MODIFY — add _verify_references method)
  Depends on:        None
  Required Tests:
    | Test ID            | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-------------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-112-01-01     | unit | _verify_references exists on orchestrator | Method missing | Remove method definition | assert hasattr(orchestrator, '_verify_references') |
    | TEST-112-01-02     | unit | Verification runs without crashing on empty input | AttributeError on None | Pass None instead of proposal text | No exception raised |
    | TEST-112-01-03     | unit | Verification logs warning on low trust score | Warning not emitted | Set trust_score to 0.3 | assert "trust score" in caplog.text |
    | TEST-112-01-04     | unit | Verification does not block pipeline (HB-01) | Pipeline halts | Raise exception in verifier | Pipeline continues, error logged |
    | TEST-112-01-05     | unit | Verification accepts high trust score without modification | Citations incorrectly stripped | Set trust_score to 1.0 | Proposal sections unchanged |
    | TEST-112-01-06     | unit | Corpus papers are passed as list of dicts | TypeError on Paper objects | Pass Paper objects instead of dicts | No TypeError |
    | TEST-112-01-07     | unit | Verification runs after synthesis (HB-02) | Runs before synthesis | Mock synthesizer to fail | Verifier called after synthesizer |
    | TEST-112-01-08     | unit | Stripped proposals still valid markdown | Malformed markdown output | Inject citations in headers | Headers preserved after strip |
  Acceptance Criteria:
    AC-01: _verify_references method exists and is called after synthesis
    AC-02: Pipeline does not crash when verification fails (HB-01)
    AC-03: Unverifiable citations are replaced with [Citation needed] markers
  Traceability:
    AC-01 → TEST-112-01-01, TEST-112-01-07
    AC-02 → TEST-112-01-02, TEST-112-01-04
    AC-03 → TEST-112-01-03, TEST-112-01-05

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Reference verification wired into orchestrator
  BAC-02: All 8 tests pass
  BAC-03: CHANGELOG.md updated with BATCH-112 entry
  BAC-04: All documents archived under /docs/aiv/BATCH-112/

═══════════════════════════════════════════════════════════
```

---

## BATCH-113: Citation Grounding in Gap Analysis

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID:                 BATCH-113
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Add citation grounding to the gap analysis prompt so gaps reference
actual papers from the corpus instead of inventing references.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Modify GAP_ANALYSIS_PROMPT to instruct the LLM to only reference
    papers from the provided cluster summaries
  - Add citation integrity instruction similar to synthesis prompt
  - Pass paper titles + authors to the gap analyzer prompt

What the code MUST NOT do:
  - Must NOT change the clustering algorithm
  - Must NOT change the ResearchGap data model

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Gap analysis must still produce gaps even if no papers are provided
  HB-02: Prompt changes must not reduce gap quality (still 5-7 per run)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,252
  Expected delta:                  +8
  Expected total at Batch close:   2,260

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Harden Gap Analysis Prompt with Citation Integrity
  Priority:          High
  Description:       Modify GAP_ANALYSIS_PROMPT in gap_analyzer.py to:
                     1. Add explicit instruction: "Only reference papers listed
                        in the sample papers below. Do not invent citations."
                     2. Include paper author names in the formatted summaries
                     3. Add "CITATION INTEGRITY" section similar to synthesis prompt
  Files in scope:
    - backend/pipeline/gap_analysis/gap_analyzer.py (MODIFY)
  Depends on:        None
  Required Tests:
    | Test ID            | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-------------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-113-01-01     | unit | GAP_ANALYSIS_PROMPT contains citation integrity instruction | Instruction missing | Remove "CITATION INTEGRITY" text | assert "CITATION INTEGRITY" in GAP_ANALYSIS_PROMPT |
    | TEST-113-01-02     | unit | _format_paper_summaries includes author names | Authors not shown | Remove author formatting | assert "Author" in formatted or author in formatted |
    | TEST-113-01-03     | unit | Prompt still works with empty papers list (HB-01) | IndexError on empty list | Pass [] as papers | No exception, prompt contains context |
    | TEST-113-01-04     | unit | Prompt instructs not to invent citations | Instruction absent | Remove "Do not invent" text | assert "do not invent" in prompt.lower() or "Only reference" in prompt |
    | TEST-113-01-05     | unit | Paper summaries include year for citation grounding | Year missing | Remove year formatting | assert "2024" in formatted or "Year" in formatted |
    | TEST-113-01-06     | unit | GapAnalyzer still initializes with provider | TypeError on construction | Pass None as provider | Object created (may fail on analyze, not init) |
    | TEST-113-01-07     | unit | _format_paper_summaries respects 30-paper limit | More than 30 formatted | Pass 50 papers | assert count of numbered entries <= 30 |
    | TEST-113-01-08     | unit | Gap type values are still valid | Invalid gap types | Check allowed types | All gaps have types in [theoretical, methodological, empirical, cross-domain] |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Gap analysis prompt includes citation integrity instructions
  BAC-02: All 8 tests pass
  BAC-03: CHANGELOG.md updated
  BAC-04: All documents archived under /docs/aiv/BATCH-113/

═══════════════════════════════════════════════════════════
```

---

## BATCH-114: ProposalDeepener Pipeline Stage

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID:                 BATCH-114
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07
Task Sequencing:          Sequential

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Create a ProposalDeepenerStage that runs after synthesis and enriches
each proposal with concrete architecture, toy example, failure modes,
and measurable success criteria.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Create a new PipelineStage subclass: ProposalDeepenerStage
  - Register it in _STAGE_ORDER between proposal_synthesis and export
  - Run ProposalDeepener on each generated proposal
  - Store deepened content as additional proposal metadata

What the code MUST NOT do:
  - Must NOT modify the existing proposal synthesizer
  - Must NOT block the pipeline if deepening fails (HB-01)
  - Must NOT require an LLM call in template mode (works without provider)

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Deepening failure MUST NOT halt the pipeline
  HB-02: Deepening MUST NOT overwrite the original proposal text
         (it adds supplementary sections, doesn't replace)

───────────────────────────────────────────────────────────
DATA MODELS
───────────────────────────────────────────────────────────
  Proposal DB model has: content_md (Text), metadata (Text/JSON)
  Deepened content stored in: metadata.deepened sections
  DeepenedProposal dataclass: architecture, toy_example, failure_modes, success_criteria

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline at Blueprint issuance:  2,260
  Expected delta:                  +7
  Expected total at Batch close:   2,267

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Create ProposalDeepenerStage
  Priority:          Critical
  Description:       Create backend/pipeline/stages.py ProposalDeepenerStage class
                     that wraps ProposalDeepener. It runs after synthesis, takes each
                     proposal, deepens it in template mode (no LLM), and stores the
                     result in proposal metadata under "deepened" key.
  Files in scope:
    - backend/pipeline/stages.py (MODIFY — add ProposalDeepenerStage)
    - backend/pipeline/orchestrator.py (MODIFY — add to _STAGE_ORDER)
  Depends on:        None
  Required Tests:
    | Test ID            | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-------------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-114-01-01     | unit | ProposalDeepenerStage class exists   | ImportError | Remove class file | import succeeds |
    | TEST-114-01-02     | unit | Stage runs without crashing (HB-01)  | Exception blocks pipeline | Raise in deepener | Pipeline continues |
    | TEST-114-01-03     | unit | Template mode produces all 4 sections | Missing sections | Remove one section from template | assert all 4 fields non-empty |
    | TEST-114-01-04     | unit | Deepened content stored in metadata  | Data lost | Skip metadata write | assert "deepened" in metadata |
    | TEST-114-01-05     | unit | Original proposal text unchanged (HB-02) | Content overwritten | Compare before/after | assert before == after |
    | TEST-114-01-06     | unit | _STAGE_ORDER includes deepening     | Stage not in order | Remove from _STAGE_ORDER | assert "proposal_deepening" in _STAGE_ORDER |
    | TEST-114-01-07     | unit | Stage positioned after synthesis     | Wrong order | Move before synthesis | assert index after proposal_synthesis |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: ProposalDeepenerStage wired into _STAGE_ORDER
  BAC-02: All 7 tests pass
  BAC-03: CHANGELOG.md updated
  BAC-04: All documents archived under /docs/aiv/BATCH-114/

═══════════════════════════════════════════════════════════
```

---

## BATCH-115: Evaluation Plan Generator

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID:                 BATCH-115
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Add an evaluation plan generator that produces concrete metrics,
baselines, and ablation designs for each proposal. This directly
addresses the reviewer concern: "What would constitute a successful
implementation?"

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Create EvaluationPlanGenerator that takes a proposal's method section
    and produces structured evaluation criteria
  - Output: datasets, baselines, metrics with formulas, ablation experiments
  - Store as proposal metadata under "evaluation_plan" key
  - Template mode works without LLM

What the code MUST NOT do:
  - Must NOT require the LLM provider to be available
  - Must NOT modify the proposal synthesizer

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Generator failure must not halt the pipeline

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline:  2,267
  Expected delta: +7
  Expected total: 2,274

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Create EvaluationPlanGenerator
  Priority:          High
  Description:       Create backend/pipeline/evaluation/plan_generator.py with
                     EvaluationPlanGenerator class. In template mode, it generates
                     a structured evaluation plan from the proposal's method text.
  Files in scope:
    - backend/pipeline/evaluation/plan_generator.py (NEW)
  Depends on:        None
  Required Tests:
    | Test ID            | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-------------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-115-01-01     | unit | EvaluationPlanGenerator exists       | ImportError | Rename file | import succeeds |
    | TEST-115-01-02     | unit | Template mode produces evaluation plan | Empty output | Return empty string | assert len(plan.datasets) > 0 |
    | TEST-115-01-03     | unit | Plan includes datasets section       | Missing datasets | Skip dataset gen | assert plan.datasets is not empty |
    | TEST-115-01-04     | unit | Plan includes baselines section      | Missing baselines | Skip baseline gen | assert plan.baselines is not empty |
    | TEST-115-01-05     | unit | Plan includes metrics with targets   | No numeric targets | Return None for targets | assert any target > 0 |
    | TEST-115-01-06     | unit | Plan includes ablation experiments   | Missing ablations | Skip ablation | assert len(plan.ablations) >= 2 |
    | TEST-115-01-07     | unit | Generator handles empty input (HB-01) | Crash on empty | Pass empty string | Returns default plan, no exception |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: EvaluationPlanGenerator produces structured plans
  BAC-02: All 7 tests pass
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-115/

═══════════════════════════════════════════════════════════
```

---

## BATCH-116: PipelineEvaluator Integration + Gold Standards

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID:                 BATCH-116
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Wire PipelineEvaluator into the orchestrator so every run produces
a quality report (precision, recall, novelty rate). Create domain-
specific gold-standard gap lists for known research areas.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add _evaluate_pipeline() to orchestrator that runs after all stages complete
  - Create gold-standard gap lists for 3 domains: AI/NLP, AI/Reasoning, Biomedical
  - Store evaluation report as pipeline run metadata
  - Log quality score at pipeline completion

What the code MUST NOT do:
  - Must NOT block pipeline if evaluation fails
  - Must NOT change gap or idea generation logic

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Evaluation failure must not halt the pipeline

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline:  2,274
  Expected delta: +7
  Expected total: 2,281

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Wire PipelineEvaluator + Create Gold Standards
  Priority:          High
  Description:       Add _evaluate_pipeline() to orchestrator. Create
                     backend/pipeline/verification/gold_standards.py with
                     domain-specific known-gap lists. Run evaluator after
                     export stage and log results.
  Files in scope:
    - backend/pipeline/orchestrator.py (MODIFY — add _evaluate_pipeline)
    - backend/pipeline/verification/gold_standards.py (NEW)
  Depends on:        None
  Required Tests:
    | Test ID            | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    |:-------------------|:-----|:-------------------------------------|:------------------------------|:--------------------------------------|:-------------------------------------|
    | TEST-116-01-01     | unit | Gold standards exist for 3+ domains  | Missing domains | Remove a domain | assert len(GOLD_STANDARDS) >= 3 |
    | TEST-116-01-02     | unit | AI/NLP gold standard has 5+ gaps     | Insufficient gaps | Remove gaps | assert len(gold["AI/NLP"]) >= 5 |
    | TEST-116-01-03     | unit | PipelineEvaluator runs on orchestrator | Not wired | Remove method | assert hasattr(orchestrator, '_evaluate_pipeline') |
    | TEST-116-01-04     | unit | Evaluation produces quality score    | No score | Return None | assert 0 <= score <= 1.0 |
    | TEST-116-01-05     | unit | Evaluation does not block (HB-01)    | Pipeline halts | Raise exception | Pipeline completes |
    | TEST-116-01-06     | unit | Evaluation report stored in metadata | Data lost | Skip write | assert "quality_report" in metadata |
    | TEST-116-01-07     | unit | Keyword overlap computes correctly  | Wrong overlap | Change overlap calc | overlap("a b c", "b c d") == 0.5 |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: PipelineEvaluator wired and produces quality reports
  BAC-02: Gold standard gap lists exist for 3 domains
  BAC-03: All 7 tests pass
  BAC-04: Documents archived under /docs/aiv/BATCH-116/

═══════════════════════════════════════════════════════════
```

---

## BATCH-117: Cross-Run Gap Deduplication

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID:                 BATCH-117
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Add cross-run gap deduplication so overlapping gaps from different
pipeline runs are merged rather than counted as separate discoveries.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Create GapDeduplicator that compares gaps across runs using title similarity
  - Threshold: gaps with >0.6 word overlap are considered duplicates
  - Store canonical gap + merge metadata (which runs contributed)
  - API endpoint returns deduplicated gaps by default

What the code MUST NOT do:
  - Must NOT delete original gap records (they stay per-run)
  - Must NOT modify the gap analyzer

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Deduplication must not lose unique gaps (only merge near-duplicates)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline:  2,281
  Expected delta: +7
  Expected total: 2,288

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Create GapDeduplicator
  Priority:          High
  Description:       Create backend/pipeline/gap_analysis/deduplicator.py.
                     Uses _title_similarity (already in gap_analyzer.py)
                     with a 0.6 threshold. Produces deduplicated gap lists
                     with merge metadata.
  Files in scope:
    - backend/pipeline/gap_analysis/deduplicator.py (NEW)
  Depends on:        None
  Required Tests:
    | Test ID            | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    | TEST-117-01-01     | unit | Identical gaps are merged            | Not merged | Change threshold to 1.0 | assert len(deduped) < len(input) |
    | TEST-117-01-02     | unit | Unique gaps are preserved (HB-01)    | Unique lost | Add unique gap | assert unique gap in result |
    | TEST-117-01-03     | unit | Threshold 0.6 merges "cost efficiency" and "cost-efficient reasoning" | Not merged | Set threshold to 1.0 | assert merged count >= 1 |
    | TEST-117-01-04     | unit | Merge metadata includes source run IDs | Metadata lost | Skip metadata write | assert "source_run_ids" in merged |
    | TEST-117-01-05     | unit | Empty input returns empty            | Crash on [] | Pass [] | assert result == [] |
    | TEST-117-01-06     | unit | Single gap returns unchanged         | Single gap merged | Pass 1 gap | assert len(result) == 1 |
    | TEST-117-01-07     | unit | Dedup works across 3+ runs          | Only works for 2 | Pass gaps from 3 runs | Correct merge count |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: GapDeduplicator merges near-duplicate gaps
  BAC-02: All 7 tests pass
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-117/

═══════════════════════════════════════════════════════════
```

---

## BATCH-118: Ideator Agent Prompt Hardening

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID:                 BATCH-118
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Harden the ideator agent prompt to produce more concrete ideas
with preliminary architecture sketches and measurable criteria.
Add citation integrity instructions.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What the code MUST do:
  - Add citation integrity instruction to ideator_system.md
  - Add instruction for concrete architecture components in ideas
  - Add instruction for measurable success criteria in ideas
  - Require ideas to specify expected failure modes

What the code MUST NOT do:
  - Must NOT change the IdeaCandidate data model
  - Must NOT change the tree search engine

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────
  HB-01: Prompt changes must not reduce idea generation rate

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────
  Baseline:  2,288
  Expected delta: +4
  Expected total: 2,292

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: Harden Ideator System Prompt
  Priority:          High
  Description:       Modify backend/pipeline/generation/prompts/ideator_system.md
                     to include: citation integrity, concrete architecture
                     requirements, measurable criteria, failure mode analysis.
  Files in scope:
    - backend/pipeline/generation/prompts/ideator_system.md (MODIFY)
  Depends on:        None
  Required Tests:
    | Test ID            | Type | Behavior Verified                    | Failure Mode                  | Falsified By                          | Pass Criteria                        |
    | TEST-118-01-01     | unit | Prompt contains citation integrity   | Missing | Remove text | assert "citation" in prompt.lower() |
    | TEST-118-01-02     | unit | Prompt requires architecture details | Missing | Remove section | assert "architecture" in prompt.lower() or "component" in prompt.lower() |
    | TEST-118-01-03     | unit | Prompt requires failure modes        | Missing | Remove section | assert "failure" in prompt.lower() |
    | TEST-118-01-04     | unit | Prompt still contains n_ideas variable | Template broken | Remove variable | assert "n_ideas" in prompt or "{{ n_ideas }}" in prompt |

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Ideator prompt hardened with citation integrity + depth instructions
  BAC-02: All 4 tests pass
  BAC-03: CHANGELOG.md updated
  BAC-04: Documents archived under /docs/aiv/BATCH-118/

═══════════════════════════════════════════════════════════
```

---

## BATCH-119: Real Pipeline Run with All Quality Gates

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID:                 BATCH-119
Blueprint Version:        1.0
Cycle Mode:               SIMPLIFIED
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07

SIMPLIFIED CYCLE ELIGIBILITY:
  [x] Exactly 1 Task
  [x] No existing source files modified (documentation/test only)
  [x] No Hard Boundaries required
  [x] Single deliverable: pipeline run with quality report

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Run a real pipeline with all Phase 8 quality gates active.
Verify: reference verification logs, proposal deepening output,
pipeline quality score, and gap deduplication across runs.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────
What MUST happen:
  - Pipeline runs on a concrete topic with all new stages active
  - Reference verification runs and logs trust score
  - Proposal deepening adds architecture + failure modes
  - Pipeline evaluator produces quality report
  - Gap deduplication merges overlapping gaps from prior runs

What MUST NOT happen:
  - Pipeline must not crash on any new stage

───────────────────────────────────────────────────────────
TASK DEFINITION
───────────────────────────────────────────────────────────
  Description:      Run pipeline on "Neuro-Symbolic Graph Reasoning"
                    with deep_research strategy. Verify all quality gates fire.
  Files in scope:   sessions/260501-ivory-wolf/data/batch119_quality_report.md (NEW)
  Priority:         Critical
  Required Tests:   NONE — this is a live validation run, tests are the pipeline itself
  Acceptance Criteria:
    AC-01: Pipeline completes without error
    AC-02: Reference verification logs a trust score
    AC-03: At least 1 proposal has deepened content in metadata
    AC-04: Pipeline evaluator produces a quality score between 0 and 1
    AC-05: Quality report written to disk

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Pipeline run completes successfully
  BAC-02: Quality report exists on disk
  BAC-03: Documents archived under /docs/aiv/BATCH-119/

═══════════════════════════════════════════════════════════
```

---

## BATCH-120: Phase 8 Close + Quality Verification Report

```
BATCH BLUEPRINT
═══════════════════════════════════════════════════════════
Batch ID:                 BATCH-120
Blueprint Version:        1.0
Cycle Mode:               SIMPLIFIED
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-07

SIMPLIFIED CYCLE ELIGIBILITY:
  [x] Exactly 1 Task
  [x] No existing source files modified
  [x] No Hard Boundaries required
  [x] Single deliverable: Phase 8 completion report + STATE.md update

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────
Close Phase 8. Write completion report. Update STATE.md.
Verify all quality improvements are in place and test count matches.

───────────────────────────────────────────────────────────
TASK DEFINITION
───────────────────────────────────────────────────────────
  Description:      Write phase8_completion_report.md summarizing all
                    quality improvements. Update STATE.md to reflect
                    new modules. Verify test baseline matches expected count.
  Files in scope:
    - sessions/260501-ivory-wolf/data/phase8_completion_report.md (NEW)
    - docs/aiv/STATE.md (UPDATE)
  Priority:         Medium
  Required Tests:   NONE — documentation only
  Acceptance Criteria:
    AC-01: Completion report exists and covers all 8 batches
    AC-02: STATE.md updated with Phase 8 modules
    AC-03: Test count verified matches expected baseline

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────
  BAC-01: Phase 8 completion report written
  BAC-02: STATE.md reflects all new modules
  BAC-03: Documents archived under /docs/aiv/BATCH-120/

═══════════════════════════════════════════════════════════
```

---

## Summary

| Batch | Type | Tasks | Tests | Focus |
|:------|:-----|:------|:------|:------|
| B112 | STANDARD | 1 | 8 | ReferenceVerifier → orchestrator wiring |
| B113 | STANDARD | 1 | 8 | Gap analysis citation grounding |
| B114 | STANDARD | 1 | 7 | ProposalDeepener pipeline stage |
| B115 | STANDARD | 1 | 7 | Evaluation plan generator |
| B116 | STANDARD | 1 | 7 | PipelineEvaluator + gold standards |
| B117 | STANDARD | 1 | 7 | Cross-run gap deduplication |
| B118 | STANDARD | 1 | 4 | Ideator prompt hardening |
| B119 | SIMPLIFIED | 1 | 0 | Real pipeline run with quality gates |
| B120 | SIMPLIFIED | 1 | 0 | Phase 8 close + completion report |
| **TOTAL** | | **10** | **~48** | |

**Baseline:** 2,244 → **Expected close:** 2,292 (+48 tests)
