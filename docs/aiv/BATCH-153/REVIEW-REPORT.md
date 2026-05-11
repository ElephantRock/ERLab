# REVIEW REPORT — BATCH-153

**Reviewer:** AIV Framework v5.3 (Automated Review)
**Review Cycle:** 1
**Blueprint Version:** 1.0
**Date:** 2026-05-11
**Verdict:** ACCEPT WITH MODIFICATIONS

---

## CHK-00: Cycle Mode

**Result: PASS**

Cycle Mode is `STANDARD` with 4 tasks and sequential ordering (`TASK-01→TASK-02→TASK-03→TASK-04`). This is consistent with a single-feature batch that adds a new pipeline stage with supporting infrastructure. Task sequencing respects dependency chains (TASK-02 depends on TASK-01; TASK-03 and TASK-04 depend on TASK-02).

No issues.

---

## CHK-01: Batch Goal

**Result: PASS**

> "Add a paper synthesis stage that converts pipeline proposals into publication-ready LaTeX papers. The stage uses the LLM to expand proposals into full academic papers with proper structure (Abstract, Introduction, Related Work, Methodology, Experiments, Discussion, Conclusion, References). Includes venue templates (IEEE, ACM, NeurIPS) and a LaTeX export API endpoint."

The goal is **clear, deployable, and bounded**. It specifies:
- The new capability (paper synthesis stage)
- The LLM's role (expand proposals → academic prose)
- Required structure (8 academic sections)
- Deliverables (venue templates + API endpoint)

No ambiguity. A single programmer can read this and understand what to build.

---

## CHK-02: Scope Boundaries

**Result: PASS**

**MUST do (7 items):** All specific, actionable, and testable. Covers the full feature surface: synthesizer class, prompt template, pipeline stage, stage registration, venue templates, LaTeX exporter extension, and API endpoint.

**MUST NOT do (5 items):** All concrete and enforceable:
- No ProposalSynthesizer modification ✓
- No existing export format breakage ✓
- No new DB tables ✓
- No pdflatex dependency ✓
- No pipeline blocking on failure ✓

Boundaries are complete. Nothing ambiguous that a Lead could exploit to scope-creep.

---

## CHK-03: Hard Boundaries

**Result: PASS**

All 5 hard boundaries are **falsifiable** with concrete pass/fail criteria:

| Boundary | Falsification Method |
|:---------|:---------------------|
| HB-01: 2,515 tests pass | Run full test suite; any failure = HB violation |
| HB-02: LLM failure doesn't block | Mock provider to raise; pipeline must continue |
| HB-03: Valid LaTeX (no unclosed envs) | Regex check all `\begin{X}` have matching `\end{X}` |
| HB-04: No fabricated citation indices | Check all `[SOURCE-X]` indices ≤ len(source_papers) |
| HB-05: Word count ≥ 2,000 | Count words in generated paper; warn but accept if short |

Each HB is independently testable. No ambiguity in what constitutes a violation.

---

## CHK-04: Data Models

**Result: PASS (with advisory notes)**

### New Data Models

**`VenueTemplate`** (venue_templates.py) — Well-defined:
- `name: str`, `document_class: str`, `packages: list[str]`, `preamble_extra: str`, `max_pages: int | None`
- Clean dataclass, no issues.

**`PaperSynthesisResult`** (paper_synthesizer.py) — Well-defined:
- `proposal_id: int`, `paper_markdown: str`, `word_count: int`, `venue: str`, `model_used: str`, `source_count: int`
- `to_dict()` method for JSON storage — consistent with how AdversarialReviewScore works.

### Existing Module References — Verified Against Codebase

| Reference | Verified | Status |
|:----------|:---------|:-------|
| `stages.py` — PipelineStage, StageContext, AdversarialReviewStage | ✓ | Match |
| `orchestrator.py` — `_STAGE_ORDER` (11 entries) | ✓ | Match — currently 11 entries |
| `proposal_synthesizer.py` — ResearchProposal, ProposalSynthesizer | ✓ | Match |
| `latex_exporter.py` — LatexExporter, TEMPLATE | ✓ | Match — `TEMPLATE` is module-level Jinja2 string |
| `md_to_latex.py` — MarkdownToLatexConverter | ✓ | Match |
| `bibtex_exporter.py` — `paper_to_bibtex`, `papers_to_bibtex` | ✓ | Match |
| `provider_factory.py` — `get_generation_provider()` | ✓ | Exists at line 244 |
| `presets.py` — strategy presets, `_all_stages_enabled()` | ✓ | Match — 11 stages listed |

### Advisory Note (non-blocking)

**`ResearchProposal.metadata`** — The `ResearchProposal` class has **no `metadata` attribute** by default. Existing stages (AdversarialReviewStage, ProposalDeepeningStage) handle this with defensive `hasattr`/`getattr` checks and dynamically assign `proposal.metadata`. The Blueprint stores `proposal.metadata["full_paper"]` following this pattern. This is **fragile but consistent** — the Lead should follow the same defensive pattern established by AdversarialReviewStage's `_get_metadata()` / `_set_metadata()` static methods. Not a blocker since the pattern is established.

---

## CHK-05: Task Coherence, Independence, Completeness

**Result: PASS**

### Coherence

All 4 tasks contribute directly to the batch goal:
- TASK-01: Core synthesizer engine
- TASK-02: Pipeline integration + venue templates
- TASK-03: Export pipeline (LaTeX → API)
- TASK-04: Strategy wiring

### Independence

Dependency chain is clean:
```
TASK-01 (PaperSynthesizer)
  └→ TASK-02 (Stage + venue_templates)
       ├→ TASK-03 (LatexExporter + API)
       └→ TASK-04 (Strategy presets)
```

TASK-03 and TASK-04 are independent of each other (both depend only on TASK-02). Sequential ordering is correct for STANDARD mode, though TASK-03 and TASK-04 could theoretically run in parallel in a FAN-OUT cycle.

### Completeness

The task set covers the full feature surface. No missing pieces — the pipeline from synthesizer → stage → export → strategy wiring is complete.

---

## CHK-06: Test Coverage

**Result: FLAG**

### Test Tables — 6-Column Format

All test tables use the required 6-column format (Test ID, Type, Behavior Verified, Failure Mode, Falsified By, Pass Criteria). No missing columns. ✓

### FLAG-01: Test Count Mismatch

The Blueprint states:
> Expected delta (all Tasks): +18 new tests

But counting tests from task tables:
- TASK-01: 5 tests (TEST-153-01-01 through 01-05)
- TASK-02: 6 tests (TEST-153-02-01 through 02-06)
- TASK-03: 5 tests (TEST-153-03-01 through 03-05)
- TASK-04: 4 tests (TEST-153-04-01 through 04-04)

**Total: 20 tests, not 18.**

This means the expected total at batch close should be **2,535** (2,515 + 20), not **2,533** (2,515 + 18).

**Severity: Low.** Arithmetic error in metadata. The Lead should correct the TEST BASELINE section before execution.

### FLAG-02: Missing Test for literature_review Preset

AC-04-02 claims:
> "fast_scan + literature_review disable paper synthesis"

But TEST-153-04-03 only tests `fast_scan`. There is **no test** verifying that `literature_review` disables `paper_synthesis`. While this is moot in practice (literature_review already disables `proposal_synthesis`, so there are no proposals to generate papers from), the AC claims the behavior and a test should exist.

**Severity: Low.** Either add a test or amend AC-04-02 to only reference fast_scan.

---

## CHK-07: Consistency with STATE.md and Existing Codebase

**Result: FLAG**

### Consistent Items

| Check | Result |
|:------|:-------|
| Test baseline: 2,515 | ✓ Matches STATE.md and BATCH-152 close |
| `_STAGE_ORDER`: 11 entries | ✓ Matches current orchestrator.py |
| DEC-004 acknowledgment | ✓ Blueprint correctly notes 11→12 transition |
| AdversarialReviewStage pattern | ✓ TASK-02 follows established stage pattern |
| Export format preservation | ✓ MUST NOT clause covers this |
| Strategy preset structure | ✓ `_all_stages_enabled()` helper correctly identified |
| `PaperSynthesizer` uses generation provider | ✓ A-01 aligns with existing provider routing |
| `[SOURCE-X]` citation format | ✓ Consistent with BATCH-111 closed-book policy |

### FLAG-03: API Route Prefix Discrepancy

Blueprint specifies:
> `GET /api/v1/export/latex/{run_id}?venue=generic`

But existing export routes in `backend/api/routes/export.py` use prefix `/api/export`:
```python
router = APIRouter(prefix="/api/export", tags=["export"])
```

Existing routes are:
- `GET /api/export/markdown/{run_id}`
- `GET /api/export/bibtex/{run_id}`

The new LaTeX endpoint should be:
- `GET /api/export/latex/{run_id}?venue=generic`

**Severity: Medium.** The Lead should use the `/api/export/` prefix to maintain consistency with existing routes. Using `/api/v1/export/` would create an inconsistent API surface.

### FLAG-04: Stage Ordering — Paper Synthesis Before Deepening

Authority Rule A-04 specifies:
> "paper_synthesis" appears after `adversarial_review` and before `proposal_deepening`

This means the pipeline ordering becomes:
```
... → proposal_synthesis → adversarial_review → paper_synthesis → proposal_deepening → export
```

The full paper is generated from the **post-review proposal** but **before** deepening adds architecture, toy examples, failure modes, and success criteria. The paper will therefore **not** include the deepened content.

This may be intentional — the paper follows academic structure while deepening adds planning metadata. However, it's worth confirming because:
1. The deepened architecture and toy examples would enrich a paper's Methodology and Experiments sections
2. Reversing the order (deepen → synthesize paper) would produce a more complete paper

**Severity: Advisory.** Not a blocker, but the Lead should confirm this ordering is deliberate. If the paper should include deepened content, A-04 should be revised to place paper_synthesis **after** proposal_deepening.

### FLAG-05: Preset Docstring Update Not Explicit

`presets.py` has a module-level docstring listing all 11 stages:
```python
"""
Actual stage names (from PipelineOrchestrator._STAGE_ORDER):
  0. literature_search
  ...
  10. export
"""
```

TASK-04 modifies `_all_stages_enabled()` but does not explicitly mention updating this docstring to reflect 12 stages (adding paper_synthesis at position 9). The `_all_stages_enabled()` stage_names list is the actual source of truth, so this is cosmetic — but the docstring will be stale if not updated.

**Severity: Trivial.** Mention in TASK-04 scope or accept as part of the file modification.

---

## Summary

| Check | Result | Severity | Flags |
|:------|:-------|:---------|:------|
| CHK-00: Cycle Mode | **PASS** | — | — |
| CHK-01: Batch Goal | **PASS** | — | — |
| CHK-02: Scope Boundaries | **PASS** | — | — |
| CHK-03: Hard Boundaries | **PASS** | — | — |
| CHK-04: Data Models | **PASS** | Advisory | — |
| CHK-05: Task Coherence | **PASS** | — | — |
| CHK-06: Test Coverage | **FLAG** | Low | FLAG-01, FLAG-02 |
| CHK-07: Consistency | **FLAG** | Medium | FLAG-03, FLAG-04, FLAG-05 |

### Flags Summary

| Flag | Severity | Description | Action Required |
|:-----|:---------|:------------|:----------------|
| FLAG-01 | Low | Test count mismatch: stated +18, actual +20 (2,533 → 2,535) | Correct TEST BASELINE numbers |
| FLAG-02 | Low | No test for literature_review disabling paper_synthesis (claimed in AC-04-02) | Add test or amend AC |
| FLAG-03 | Medium | API route `/api/v1/export/` inconsistent with existing `/api/export/` prefix | Use `/api/export/latex/` |
| FLAG-04 | Advisory | paper_synthesis before proposal_deepening means paper excludes deepened content | Confirm ordering is deliberate |
| FLAG-05 | Trivial | presets.py module docstring not mentioned in TASK-04 scope | Include in TASK-04 file scope notes |

---

## Verdict: **ACCEPT WITH MODIFICATIONS**

The Blueprint is structurally sound, well-scoped, and consistent with the codebase architecture. All hard boundaries are falsifiable, data models are accurate, and the task decomposition is clean.

**Required changes before execution:**
1. **FLAG-03 (Medium):** Change API route from `/api/v1/export/latex/{run_id}` to `/api/export/latex/{run_id}` for consistency
2. **FLAG-01 (Low):** Correct test delta from +18 to +20 and total from 2,533 to 2,535

**Recommended but non-blocking:**
3. **FLAG-02 (Low):** Add test for literature_review disabling paper_synthesis, or amend AC-04-02
4. **FLAG-04 (Advisory):** Confirm stage ordering (paper_synthesis before proposal_deepening) is deliberate
5. **FLAG-05 (Trivial):** Add presets.py docstring update note to TASK-04

Once FLAG-03 is addressed, the Blueprint is ready for execution.

---

*End of Review Report — BATCH-153, Cycle 1*
