# Phase 1 Closeout — Full-Paper Product Path

> **Phase 1 closeout.** Records only the fields specified in the Work Package.
> **No P1E artifact changed. No retrieval architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `e3e07bb8e8c4e1161792bac3af4bbf6682bc8d69` (Phase 0 final) |
| **Final commit** | (tip of `feat/quarantine-and-frontend-redesign` after this closeout; this file deliberately does not record its own hash — self-referentially unstable) |
| **Working tree at closeout** | clean |

---

## Files changed

**Commit 1** (`1462a22`) — `feat(pipeline): carry research questions through research runs`
- `backend/api/schemas.py`, `backend/pipeline/stages.py`, `backend/pipeline/orchestrator/_orchestrator.py`, `backend/api/routes/pipeline.py`, `backend/pipeline/export/run_artifacts.py`
- `frontend/src/api/types.ts`, `frontend/src/components/pipeline/run-config-form.tsx`, `frontend/src/components/pipeline/__tests__/batch141-strategy-default.test.tsx`

**Commit 2** (`f427f4e`) — `feat(paper): expose existing paper synthesis and evaluation artifacts`
- `backend/db/models.py`, `alembic/versions/031_proposal_paper_columns.py`, `backend/pipeline/persistence.py`, `backend/api/routes/ideas.py`, `backend/pipeline/stages.py`, `backend/api/routes/paper_export.py`, `backend/api/app.py`

**Commit 3** (`bef8205`) — `feat(frontend): add full-paper review and export workflow`
- `frontend/src/api/types.ts`, `frontend/src/api/exports.ts`, `frontend/src/components/ideas/paper-workspace.tsx`, `frontend/src/pages/idea-detail.tsx`
- backend mount fix: `backend/api/routes/paper_export.py`, `backend/api/app.py`

**Commit 4** (this closeout) — `test(project): seal Phase 1 full-paper product path`
- focused tests + this closeout

## Existing paper path discovered (1A)

The 1A trace materially changed what "expose existing" meant. *[VERIFIED]*

1. **Does every `deep_research` run execute paper synthesis?** YES for `deep_research` and `academic_proposal`; NO for `fast_scan` and `literature_review` (`pipeline.yaml` + `presets.py`).
2. **Where is the final paper stored?** It was NOT stored. `PaperSynthesisStage` wrote `proposal.metadata["full_paper"]` in memory; `persist_proposals` dropped `metadata` entirely. No DB column, no disk file.
3. **Associated with run, idea, or both?** One paper per Proposal/Idea (`Proposal.idea_id` unique). Relationship: PipelineRun → Ideas → Proposals.
4. **Does the API return the paper?** NO — no field existed in any schema or route.
5. **Does any evaluator consume the paper?** NO. The only LLM evaluator consumed PROPOSAL markdown and ran BEFORE `paper_synthesis` in stage order.
6. **Which export formats accept the paper?** Only LaTeX's venue path read it (and only from in-memory proposals, unreachable from DB-loaded ones). Markdown ignored it; `BibTeXExporter` did not exist (the `paper_to_bibtex` function takes source literature).

**Consequence:** "expose existing" required (a) a real persistence home, (b) a thin paper-level evaluation adapter, (c) paper-aware export endpoints. This is integration/exposure work, not new synthesis — the `PaperSynthesizer` itself was reused unchanged.

## Research-question path (1B)

`research_question: str | None` threaded: API request → `config_json` (persisted) → orchestrator.run → StageContext → LiteratureSearchStage (seeds derived queries + anchors LLM expansion when no explicit `search_queries`) → ProposalSynthesisStage (prepended into `framing_directive`) → `brief.json`. Materially influences the run; not display-only. Legacy domain-only requests unchanged.

## Paper persistence path (1C)

- Migration 031: `Proposal.paper_md` + `Proposal.paper_meta_json` (nullable).
- `_extract_paper_artifact()` normalizes the in-memory `full_paper` dict; `persist_proposals` now writes both columns.
- State machine exposed on idea-detail: `not_requested | pending | ready | failed`. **Empty/placeholder paper recorded as `failed`, never `ready`.**

## Paper evaluation scope (1D)

Thin adapter `PaperSynthesisStage._evaluate_paper()` reuses `ProposalEvaluator` on the synthesized paper markdown — no new dimensions, thresholds, or framework. Runs after synthesis; scoped explicitly as `scope: paper`, labeled "Paper evaluation" in the UI and distinct from the proposal evaluation. Failure is non-fatal (`status: failed`) and never blocks viewing/exporting a generated paper.

## Exports exposed (1F)

`/api/v1/export/paper/{markdown,latex,bibtex}/{idea_id}` — operate on the persisted final paper only; 404 when absent; stable filenames; never export proposal text under a paper filename.

## End-to-end result

Deterministically verified via the 1G focused tests (the acceptance scenario's invariants): research question accepted and threaded → paper synthesized and persisted non-empty → paper state serialized correctly → paper evaluation scope=paper → Markdown/LaTeX/BibTeX exports return paper content → missing paper returns explicit 404. The historical GoT × NSR paper remains a workflow fixture (not a quality oracle, per Phase 0 correction).

## Backend focused tests (1G)

| File | Tests | Covers cases |
|---|---|---|
| `test_api/test_phase1_research_question.py` | 7 | 1, 2, 3 (+ length limit, context threading) |
| `test_pipeline/test_phase1_paper_persistence.py` | 9 | 4, 5, 6, 7, 8 (empty→failed, absent→null, scope distinct) |
| `test_api/test_phase1_paper_export.py` | 7 | 9, 10, 11, 12 (md/latex/bibtex content; 404 on missing) |
| **Total new** | **23** | **all 12 backend cases** |

## Architecture tests

**41 passed, 0 failed.** (P0.5 seal green from Phase 0; no Phase 1 change touches sealed code paths.)

## Ranking tests

**253 passed, 3 skipped** (closeout-mode gated). No P1E artifact changed.

## Full backend selector

**136 failed, 4603 passed, 47 skipped, 29 deselected** (253 s).

- **136 failed — IDENTICAL to Phase 0 baseline** (same count, same subsystem distribution: test_pipeline 73, test_api 23, test_providers 14, test_operations 14, test_literature 12).
- **0 failures attributable to Phase 1** — no Phase 1 test or touched subsystem (`phase1`, `paper_export`, `paper_persistence`, `research_question`, `ideas.py`) appears in the failure set.
- **+23 passed vs Phase 0** (4580 → 4603), matching the new focused tests.
- The 136 remain the tracked test-isolation debt from Phase 0 (classification unchanged: runtime defect not established; isolation defect strongly indicated; full-suite health failing; blocks Phase 1: no; must remain tracked: yes).

## Frontend tests / build / budgets

| Check | Result |
|---|---|
| Typecheck (`tsc -b`) | **PASS** — clean |
| Tests (`vitest run`) | **123 files, 996 passed, 0 failed** (was 984 at Phase 0; +12 from PaperWorkspace tests) |
| Production build (`vite build`) | **PASS** — 17.45 s |
| Lint (`eslint .`) | **0 errors, 63 warnings** (matches Phase 0; no new debt) |
| TS / API / lint budget ratchets | **all hold** (0 errors / 0 unchecked / lint budget holds at 59) |

One Phase-1-intended test update: `batch144-form-density` raised the pre-advanced field count from 2 → 3 (research question is now a primary field) — a deliberate contract change, not a workaround.

## Known limitations

1. **136 backend full-suite failures** — unchanged from Phase 0 baseline; tracked test-isolation debt; not Phase-1-attributable.
2. **Paper LaTeX export** wraps the paper markdown in a minimal article shell (intentional — full markdown→LaTeX conversion is out of Phase 1 scope; the export is honest about what it contains).
3. **Paper-level evaluation reuses the proposal evaluator's dimensions** — the spec explicitly forbade new dimensions/frameworks; the 7 existing dimensions (novelty, feasibility, completeness, rigor, clarity, baseline_adequacy, compute_realism) are applied to paper text, scoped as `paper`.
4. **End-to-end run was not executed live** — the acceptance scenario's invariants are verified deterministically via focused tests with controlled fixtures, per the spec ("Use deterministic test providers or existing controlled fixtures"). A live E2E run belongs in Phase 3 (product comparison).
5. **`paper_evaluation` runs inside `PaperSynthesisStage`** rather than as a separate stage — the smallest change that preserves correct ordering (after synthesis); a separate `PaperEvaluationStage` is a Phase 2+ refinement, not a Phase 1 requirement.

## P1E artifacts changed = 0

Confirmed: no file under `data/evaluation/`, `docs/research/`, or `docs/retrieval/` was modified. All Phase 1 changes are in `backend/` (pipeline/api/db), `frontend/`, `alembic/versions/031_*`, and `docs/project/phase1/`.

## Working tree status

**clean** at closeout.

---

## Phase 1 completion criteria *[VERIFIED]*

| Criterion | Status |
|---|---|
| Natural-language question accepted through UI | ✅ research-question textarea is the primary input |
| Question materially reaches pipeline context | ✅ threaded to search + synthesis (not display-only) |
| Legacy domain workflow preserved | ✅ domain-only requests unchanged; 7 tests confirm |
| Existing PaperSynthesizer used | ✅ reused unchanged; only persistence/exposure added |
| Non-empty final paper visible through UI | ✅ PaperWorkspace renders paper_md when status=ready |
| Paper evaluation based on final paper text | ✅ thin adapter reuses ProposalEvaluator on paper markdown |
| Evaluation scope labeled truthfully | ✅ "Paper evaluation" + scope:paper, distinct from proposal |
| Citation status visible | ✅ unresolved count rendered from citation_audit |
| Markdown export works | ✅ /export/paper/markdown/{id} |
| LaTeX export works | ✅ /export/paper/latex/{id} |
| BibTeX export works | ✅ /export/paper/bibtex/{id} |
| Failure states explicit | ✅ not_requested/pending/failed each show actionable message |
| Architecture seals pass | ✅ 41/41 |
| Ranking suite passes | ✅ 253 passed, 3 skipped |
| Frontend tests/build/budgets pass | ✅ 996 tests, build clean, all budgets hold |
| Full backend-suite state reported honestly | ✅ 136 failed (identical to baseline; 0 Phase-1-attributable) |
| No P1E artifact changed | ✅ |
| No retrieval architecture changed | ✅ |
| Working tree clean | ✅ |

---

*End of Phase 1.*
