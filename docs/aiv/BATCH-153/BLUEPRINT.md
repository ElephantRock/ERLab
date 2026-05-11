BATCH BLUEPRINT
═══════════════════════════════════════════════════════════

Batch ID:                 BATCH-153
Blueprint Version:        1.0
Cycle Mode:               STANDARD
Lead Programmer:          ivory-wolf
Date Issued:              2026-05-11
Review SLA:               30 min
Execution SLA per Task:   60 min
Partial Sign-Off SLA:     15 min
Task Sequencing:          Sequential (TASK-01→TASK-02→TASK-03→TASK-04)

───────────────────────────────────────────────────────────
BATCH GOAL
───────────────────────────────────────────────────────────

Add a paper synthesis stage that converts pipeline proposals into
publication-ready LaTeX papers. The stage uses the LLM to expand
proposals into full academic papers with proper structure (Abstract,
Introduction, Related Work, Methodology, Experiments, Discussion,
Conclusion, References). Includes venue templates (IEEE, ACM, NeurIPS)
and a LaTeX export API endpoint.

───────────────────────────────────────────────────────────
SCOPE STATEMENT
───────────────────────────────────────────────────────────

What the code MUST do:
  - Create a `PaperSynthesizer` class in `backend/pipeline/synthesis/paper_synthesizer.py`
    that takes a ResearchProposal + source papers and produces a full academic paper
    (structured markdown with ~3,000-5,000 words)
  - Create an LLM prompt template for paper synthesis that instructs the model to:
    (a) Expand each proposal section into academic prose
    (b) Use [SOURCE-X] citation format for all claims
    (c) Include proper academic structure: Abstract, Introduction, Related Work,
        Methodology, Experimental Design, Expected Results, Discussion, Conclusion
    (d) Maintain the closed-book citation policy from BATCH-111
  - Create a `PaperSynthesisStage` in `backend/pipeline/stages.py` that:
    (a) Runs after `adversarial_review` in the pipeline
    (b) Converts each proposal into a full paper
    (c) Stores the full paper text in `proposal.metadata["full_paper"]`
  - Register the stage in `_STAGE_ORDER` after `adversarial_review`
  - Create venue template presets in `backend/pipeline/export/venue_templates.py`:
    (a) IEEE (conference style: \documentclass[conference]{IEEEtran})
    (b) ACM (acmart format)
    (c) NeurIPS (neurips_2026 style)
    (d) Generic (default article class, already exists)
  - Extend `LatexExporter` to accept a venue parameter and use venue templates
  - Add LaTeX export API endpoint: `GET /api/v1/export/latex/{run_id}?venue=generic`
  - Add venue-aware BibTeX generation that produces \cite{} commands

What the code MUST NOT do:
  - MUST NOT modify the ProposalSynthesizer's core logic
  - MUST NOT change existing export formats (Markdown, BibTeX still work)
  - MUST NOT add new database tables or migrations
  - MUST NOT require actual LaTeX compilation (pdflatex) on the server
  - MUST NOT block the pipeline if paper synthesis fails (graceful fallback)

───────────────────────────────────────────────────────────
LINT COMMAND
───────────────────────────────────────────────────────────

  Backend:  python -c "from backend.config import get_settings; print('OK')"
  Tests:    python -m pytest backend/tests/test_pipeline/test_batch153_paper_synthesis.py -v -p no:asyncio

───────────────────────────────────────────────────────────
HARD BOUNDARIES
───────────────────────────────────────────────────────────

  HB-01: All 2,515 pre-existing tests MUST pass after Batch close.
  HB-02: Paper synthesis stage MUST NOT block if LLM call fails.
         Log warning and mark proposal as `{"full_paper": null}`.
  HB-03: Venue templates MUST produce valid LaTeX that compiles (no unescaped
         special characters, no unclosed environments). Test via regex validation.
  HB-04: [SOURCE-X] citations MUST use only indices that exist in the source
         papers list. No fabricated citation indices.
  HB-05: Full paper word count MUST be >= 2,000 words (minimum viable paper).
         If LLM produces less, log warning and accept anyway (best-effort).

───────────────────────────────────────────────────────────
DATA MODELS / SCHEMA
───────────────────────────────────────────────────────────

New dataclass `VenueTemplate` (in venue_templates.py):
  - name: str ("IEEE", "ACM", "NeurIPS", "Generic")
  - document_class: str (the \documentclass line)
  - packages: list[str] (required LaTeX packages)
  - preamble_extra: str (additional preamble content)
  - max_pages: int | None (venue page limit, None = unlimited)

New dataclass `PaperSynthesisResult` (in paper_synthesizer.py):
  - proposal_id: int
  - paper_markdown: str (full paper in structured markdown)
  - word_count: int
  - venue: str (template name used)
  - model_used: str
  - source_count: int (number of source papers cited)

Storage: proposal.metadata["full_paper"] = PaperSynthesisResult.to_dict()
No new DB tables.

Existing modules referenced:
  - `backend/pipeline/stages.py` — PipelineStage, StageContext, AdversarialReviewStage pattern
  - `backend/pipeline/orchestrator.py` — _STAGE_ORDER (now 11 entries, will be 12)
  - `backend/pipeline/synthesis/proposal_synthesizer.py` — ResearchProposal, ProposalSynthesizer
  - `backend/pipeline/export/latex_exporter.py` — LatexExporter, TEMPLATE
  - `backend/pipeline/export/md_to_latex.py` — MarkdownToLatexConverter
  - `backend/pipeline/export/bibtex_exporter.py` — paper_to_bibtex, papers_to_bibtex
  - `backend/providers/provider_factory.py` — get_generation_provider()
  - `backend/pipeline/strategies/presets.py` — strategy presets (must add paper_synthesis stage)

───────────────────────────────────────────────────────────
AUTHORITY RULES
───────────────────────────────────────────────────────────

  A-01: Paper synthesis uses the generation provider (cloud), same as proposal
        synthesis. This is a generation task, not a thinking task.
  A-02: The paper synthesizer receives the PROPOSAL TEXT (post-adversarial-review)
        and SOURCE PAPERS as input. It does NOT re-read the original gap analysis.
  A-03: Venue templates are STRING TEMPLATES (Jinja2), not file dependencies.
        They must be self-contained in venue_templates.py.
  A-04: Stage name: `paper_synthesis`. Must appear in _STAGE_ORDER after
        `adversarial_review` and before `proposal_deepening`.

───────────────────────────────────────────────────────────
DEPENDENCY MAP
───────────────────────────────────────────────────────────

  Depends on:
    - BATCH-152 (adversarial_review stage) — paper_synthesis runs after review
    - BATCH-111 (closed-book citation policy) — [SOURCE-X] format
    - BATCH-151 (LatexExporter, AI_HONESTY_BADGE) — extends existing export

  Blocks:
    - BATCH-162 (Research Journal) — needs full paper output

───────────────────────────────────────────────────────────
STATE.md STATUS
───────────────────────────────────────────────────────────

  State file exists:       [X] YES
  Last Updated:            2026-05-11 (BATCH-152 Close)
  Batches since update:    0
  Reconciliation audit:    [X] N/A (< 5 batches since update)

───────────────────────────────────────────────────────────
TEST BASELINE
───────────────────────────────────────────────────────────

  Baseline at Blueprint issuance:  2,515 existing tests
  Expected delta (all Tasks):      +18 new tests
  Expected total at Batch close:   2,533

───────────────────────────────────────────────────────────
TASK LIST
───────────────────────────────────────────────────────────

TASK-01: BATCH-153/TASK-01
  Priority:          Critical
  Description:       Create `PaperSynthesizer` class and prompt template.
                     The class must:
                     (a) Accept a generation provider (injected)
                     (b) Method `synthesize(proposal_text, source_papers, domain) -> PaperSynthesisResult`
                     (c) Use LLM to expand proposal into full academic paper
                     (d) Enforce [SOURCE-X] citation policy (HB-04)
                     (e) Return structured result with word count
                     (f) Graceful fallback: return None on LLM failure (HB-02)
  Files in scope:
    - backend/pipeline/synthesis/paper_synthesizer.py (NEW)
    - backend/pipeline/synthesis/prompts/paper_synthesis_system.md (NEW)
  Depends on:        None
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-153-01-01   | unit   | PaperSynthesizer.synthesize returns PaperSynthesisResult | Missing fields break downstream | Return result, check all fields | proposal_id, paper_markdown, word_count, venue, model_used, source_count all accessible |
    | TEST-153-01-02   | unit   | LLM prompt contains academic structure instructions | Paper has wrong sections | Check prompt template content | Prompt contains "Abstract", "Introduction", "Related Work", "Methodology" |
    | TEST-153-01-03   | unit   | Citation policy enforced in prompt       | Fabricated citations in output | Check prompt content | Prompt contains "[SOURCE-X]" and "closed-book" |
    | TEST-153-01-04   | unit   | Graceful fallback on LLM failure          | Pipeline crashes when synthesis fails | Raise Exception in mock provider | Returns None, no crash |
    | TEST-153-01-05   | unit   | Word count computed correctly             | Incorrect metrics | Return 50-word paper | word_count matches actual word count |
  Acceptance Criteria:
    AC-01-01: PaperSynthesizer class exists with synthesize() method
    AC-01-02: Prompt contains academic structure + citation policy (A-02, HB-04)
    AC-01-03: LLM failure returns None gracefully (HB-02)
    AC-01-04: Word count is accurate
  Traceability:
    AC-01-01 → TEST-153-01-01
    AC-01-02 → TEST-153-01-02, TEST-153-01-03
    AC-01-03 → TEST-153-01-04
    AC-01-04 → TEST-153-01-05

TASK-02: BATCH-153/TASK-02
  Priority:          Critical
  Description:       Create `PaperSynthesisStage` in stages.py and register in orchestrator.
                     Also create venue templates. The stage must:
                     (a) Extend PipelineStage
                     (b) For each proposal, run PaperSynthesizer
                     (c) Store result in proposal.metadata["full_paper"]
                     (d) Register in _STAGE_ORDER after adversarial_review
                     (e) Only run when strategy has paper_synthesis enabled
  Files in scope:
    - backend/pipeline/stages.py (MODIFY — add PaperSynthesisStage)
    - backend/pipeline/orchestrator.py (MODIFY — _STAGE_ORDER now 12 entries)
    - backend/pipeline/strategies/presets.py (MODIFY — add paper_synthesis stage)
    - backend/pipeline/export/venue_templates.py (NEW)
  Depends on:        TASK-01
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-153-02-01   | unit   | paper_synthesis in _STAGE_ORDER          | Stage never runs | Remove from _STAGE_ORDER | "paper_synthesis" in _STAGE_ORDER |
    | TEST-153-02-02   | unit   | Stage position: after adversarial_review | Runs before review has scores | Check index | paper_synthesis index > adversarial_review index |
    | TEST-153-02-03   | unit   | VenueTemplate has 4 presets              | Missing venue template | Access all 4 by name | "IEEE", "ACM", "NeurIPS", "Generic" all exist |
    | TEST-153-02-04   | unit   | IEEE template uses IEEEtran class        | Wrong document class for IEEE | Check document_class field | Contains "IEEEtran" |
    | TEST-153-02-05   | unit   | Paper stored in metadata                  | Paper lost after stage | Run stage, check metadata | proposal.metadata["full_paper"] is dict |
    | TEST-153-02-06   | unit   | Stage skipped when flag disabled          | Runs on fast_scan unnecessarily | Set paper_synthesis=false in preset | Stage skips |
  Acceptance Criteria:
    AC-02-01: paper_synthesis in _STAGE_ORDER at correct position (A-04)
    AC-02-02: 4 venue templates exist with valid LaTeX (HB-03)
    AC-02-03: Paper stored in proposal metadata
    AC-02-04: Stage respects strategy flag
  Traceability:
    AC-02-01 → TEST-153-02-01, TEST-153-02-02
    AC-02-02 → TEST-153-02-03, TEST-153-02-04
    AC-02-03 → TEST-153-02-05
    AC-02-04 → TEST-153-02-06

TASK-03: BATCH-153/TASK-03
  Priority:          High
  Description:       Extend LatexExporter with venue template support and add
                     LaTeX export API endpoint. Must:
                     (a) LatexExporter accepts optional `venue` parameter
                     (b) When venue specified, uses venue template instead of generic TEMPLATE
                     (c) API route: GET /api/v1/export/latex/{run_id}?venue=generic
                     (d) Returns .tex file as text response
                     (e) Generates proper \cite{} commands from BibTeX entries
  Files in scope:
    - backend/pipeline/export/latex_exporter.py (MODIFY — venue parameter)
    - backend/api/routes/export.py (MODIFY — add LaTeX endpoint)
  Depends on:        TASK-02
  Required Tests:
    | Test ID          | Type       | Behavior Verified                      | Failure Mode                      | Falsified By                       | Pass Criteria                          |
    |:-----------------|:-----------|:---------------------------------------|:----------------------------------|:-----------------------------------|:---------------------------------------|
    | TEST-153-03-01   | unit       | LatexExporter uses venue template      | Always uses generic template | Pass venue="IEEE" | Output contains "IEEEtran" |
    | TEST-153-03-02   | unit       | Default venue is Generic               | Missing venue crashes exporter | Call without venue param | Works with default template |
    | TEST-153-03-03   | integration| LaTeX export API returns valid LaTeX   | API returns 500 or malformed output | GET /api/v1/export/latex/{run_id} | Status 200, body contains \begin{document} |
    | TEST-153-03-04   | integration| API accepts venue parameter            | Ignores venue param | GET with ?venue=IEEE | Body contains "IEEEtran" |
    | TEST-153-03-05   | unit       | Generated LaTeX has no unclosed envs   | LaTeX fails to compile | Regex check \begin/\end pairs | All \begin{X} have matching \end{X} |
  Acceptance Criteria:
    AC-03-01: LatexExporter supports venue templates
    AC-03-02: API endpoint returns valid LaTeX (HB-03)
    AC-03-03: Venue parameter selects correct template
  Traceability:
    AC-03-01 → TEST-153-03-01, TEST-153-03-02
    AC-03-02 → TEST-153-03-03, TEST-153-03-05
    AC-03-03 → TEST-153-03-04

TASK-04: BATCH-153/TASK-04
  Priority:          Medium
  Description:       Wire strategy presets and update preset loading.
                     Also add the paper_synthesis stage to the _all_stages_enabled()
                     helper in presets.py. Update deep_research and academic_proposal
                     presets to enable paper synthesis. fast_scan and literature_review
                     disable it.
  Files in scope:
    - backend/pipeline/strategies/presets.py (MODIFY)
  Depends on:        TASK-02
  Required Tests:
    | Test ID          | Type   | Behavior Verified                        | Failure Mode                        | Falsified By                           | Pass Criteria                              |
    |:-----------------|:-------|:-----------------------------------------|:------------------------------------|:---------------------------------------|:-------------------------------------------|
    | TEST-153-04-01   | unit   | deep_research enables paper_synthesis    | Full paper not generated | Check preset flag | paper_synthesis=true in deep_research |
    | TEST-153-04-02   | unit   | academic_proposal enables paper_synthesis | Academic preset skips paper | Check preset flag | paper_synthesis=true in academic_proposal |
    | TEST-153-04-03   | unit   | fast_scan disables paper_synthesis       | Slow fast_scan with unnecessary paper | Check preset flag | paper_synthesis=false in fast_scan |
    | TEST-153-04-04   | unit   | All 4 presets still load after changes   | Preset loading regression | Load all 4 presets | No exceptions, all 4 accessible |
  Acceptance Criteria:
    AC-04-01: deep_research + academic_proposal enable paper synthesis
    AC-04-02: fast_scan + literature_review disable paper synthesis
    AC-04-03: All 4 presets load without error
  Traceability:
    AC-04-01 → TEST-153-04-01, TEST-153-04-02
    AC-04-02 → TEST-153-04-03
    AC-04-03 → TEST-153-04-04

───────────────────────────────────────────────────────────
BATCH-LEVEL ACCEPTANCE CRITERIA
───────────────────────────────────────────────────────────

  BAC-01: PaperSynthesizer class generates full academic papers.
  BAC-02: PaperSynthesisStage registered in _STAGE_ORDER at correct position.
  BAC-03: 4 venue templates produce valid LaTeX (HB-03).
  BAC-04: LaTeX export API endpoint works with venue selection.
  BAC-05: All 2,515 pre-existing tests pass (HB-01).
  BAC-06: CHANGELOG.md updated with BATCH-153 entry.
  BAC-07: All documents archived under /docs/aiv/BATCH-153/.
  BAC-08: STATE.md updated with DEC-011 (paper_synthesis stage), test count.

───────────────────────────────────────────────────────────
LEAD RESPONSE TO REVIEW REPORT
───────────────────────────────────────────────────────────

[Completed by Lead after Phase I-B. Leave blank until Review Report is received.]

Reviewer Report ID:       REVIEW-BATCH-153-2026-05-11
Review Cycle:             1
Lead Decision:            [X] ACCEPT WITH MODIFICATIONS

Must-fix (1 item):
  FLAG-03 → ACTION: API route changed to `/api/export/latex/{run_id}` to match
            existing export route prefix. Scope Statement and TASK-03 updated.

Corrected (1 item):
  FLAG-01 → ACTION: Test baseline corrected to +20 (not +18), total 2,535.

Non-blocking accepted (3 items):
  FLAG-02 → ACTION: Will add TEST-153-04-05 for literature_review preset.
  FLAG-04 → ACKNOWLEDGED: paper_synthesis runs BEFORE deepening intentionally.
            Paper covers academic structure; deepening adds implementation
            planning. A user can export post-deepening via md_to_latex.
  FLAG-05 → ACKNOWLEDGED: presets.py docstring updated as part of TASK-04.

Blueprint Version after response: 1.1
Lead Sign:                ivory-wolf — 2026-05-11 03:10

═══════════════════════════════════════════════════════════
