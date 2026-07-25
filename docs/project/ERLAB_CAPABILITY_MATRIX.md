# ERLab Capability Matrix

> **Companion to** `ERLAB_CURRENT_STATE_REPORT.md` Part 6.
> **Status enum:** WORKING, PARTIAL, PRESENT_BUT_UNVERIFIED, NOT_EXPOSED, MISSING, UNKNOWN.
> **Do not infer UI availability merely because backend code exists.**
> All paths absolute under `C:\Next-Era\Elephant-Rock-Research-Lab\`.

## Summary Counts

| Status | Count |
|---|---|
| WORKING | 10 |
| PARTIAL | 4 |
| PRESENT_BUT_UNVERIFIED | 0 |
| NOT_EXPOSED | 7 |
| MISSING | 6 |
| UNKNOWN | 0 |
| **Total assessed** | **27** |

## Full Matrix

| # | Capability | Historical evidence | Current implementation path | Current UI exposure | Status | Tests | Known artifacts | Known gaps | Confidence |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Create a research project | None — no `ResearchProject` concept ever existed; only per-run `PipelineRun` rows | `backend/pipeline/orchestrator/_orchestrator.py` `PipelineOrchestrator.run` creates `PipelineRun` row | `/pipeline/new` (route exists, creates a *run* not a *project*) | **MISSING** | test_pipeline (247 files) | `data/runs/run_*` | No project entity; no grouping of runs | HIGH |
| 2 | Accept a research question | REPORTED — old runs took `domain` strings; no NL question field ever | `PipelineOrchestrator.run(domain=…, search_queries=[…])` | `/pipeline/new` `run-config-form.tsx`: `domain` (free text) + `search_queries` (keywords, advanced) | **PARTIAL** | test_api/pipeline | `data/runs/run_*/brief.json` | No NL research-question field; no seed-paper/URL input | HIGH |
| 3 | Accept a domain | VERIFIED — `domain` param since pre-wipe | `PipelineOrchestrator.run(domain=…)` | `/pipeline/new` domain input | **WORKING** | test_pipeline | `brief.json` | — | HIGH |
| 4 | Accept one or more seed papers | PARTIAL — `seed_papers` exists only as internal param of `CitationExplorer` (`backend/pipeline/literature/citation_explorer.py:63`), never a user input | `CitationExplorer(seed_papers=…)` internal only | NONE | **NOT_EXPOSED** | test_pipeline/citation | — | Not user-facing; no API field | HIGH |
| 5 | Discover literature | VERIFIED — `SearchService` since pre-wipe | `backend/pipeline/literature/search_service.py` (arxiv, crossref, openalex, pubmed, semantic_scholar); `LiteratureSearchStage` | `/literature` `pages/literature.tsx` → `GET /literature/search` | **WORKING** | test_literature, test_pipeline | `data/runs/run_*/log.jsonl` | — | HIGH |
| 6 | Rank literature | VERIFIED — `RelevanceFilter`, `LLMReranker`, `CrossEncoderReranker`, `TwoStageRetriever` exist internally | `backend/pipeline/literature/relevance_filter.py`, `backend/pipeline/knowledge/{retriever,reranker}.py`, `backend/pipeline/dag/trimmer.py` | NONE — no dedicated ranking screen; ideas/gaps are sortable but literature is not ranked in UI | **NOT_EXPOSED** | test_ranking (13 files), test_pipeline | `docs/p1b_snapshot/` | Configured reranker never wired (`_orchestrator.py:682`); `RelevanceFilter` inactive in production; ranking visibility absent | HIGH |
| 7 | Review sources | NONE — no source/paper review capability ever | No module, no stage, no API | NONE | **MISSING** | — | — | No backend, no UI | HIGH |
| 8 | Extract evidence | PARTIAL — `ClaimExtractor` extracts *claims*, not evidence rows; not wired into any orchestrator stage | `backend/pipeline/claims/extractor.py` (library-only, orphaned) | NONE — `evidence-panel.tsx` exists but is NOT rendered | **NOT_EXPOSED** | test_pipeline (claims) | — | No evidence-extraction endpoint; component is dead code | HIGH |
| 9 | Build evidence tables | NONE | No module | NONE | **MISSING** | — | — | No backend, no UI | HIGH |
| 10 | Build evidence packets | NONE | No module | NONE | **MISSING** | — | — | No backend, no UI | HIGH |
| 11 | Create claims | PARTIAL — `claims/` library exists (`Claim`, `ClaimExtractor`, `ClaimStore`, `ConnectionAgent`); NOT wired into orchestrator/registry; no API route | `backend/pipeline/claims/` | NONE — no `/claims` route in `app.py`, no `api/claims.ts` | **NOT_EXPOSED** | test_pipeline (claims) | — | Orphaned library; not invoked from CLI/API | HIGH |
| 12 | Create arguments | NONE | No module | NONE | **MISSING** | — | — | No backend, no UI | HIGH |
| 13 | Synthesize multiple papers | VERIFIED — `ProposalSynthesizer`, `SectionWiseSynthesizer`, `FastProposalSynthesizer`, `PaperSynthesizer` | `backend/pipeline/synthesis/` | Implicit via pipeline; output viewed at `/ideas/:id` | **WORKING** | test_generation, test_pipeline | `data/runs/run_*/proposals/*.md` | No direct "synthesize these N papers" user action | HIGH |
| 14 | Generate a proposal | VERIFIED — `ProposalSynthesisStage` + `ProposalDeepeningStage` | `backend/pipeline/synthesis/`, `backend/pipeline/verification/proposal_deepener.py` | `/ideas/:id` renders `proposal_md`/`proposal_sections`; refine via `POST /ideas/{id}/refine` | **WORKING** | test_generation, test_pipeline | 10 full proposals in `data/runs/` | — | HIGH |
| 15 | Generate a full paper | VERIFIED — `PaperSynthesizer` + `PaperSynthesisStage` exist; `run_e2e_pipeline.py` invokes `deep_research` strategy which includes `paper_synthesis` | `backend/pipeline/synthesis/paper_synthesizer.py` | NONE — UI only surfaces proposals; no paper-vs-proposal toggle | **NOT_EXPOSED** | test_pipeline/paper | Historical deleted papers in `sessions/260501-ivory-wolf/` | Backend exists; not exposed in UI | HIGH |
| 16 | Generate citations | VERIFIED — `ReferenceResolver`, `ReferenceValidator`, `[SOURCE-N]` markers | `backend/pipeline/provenance/reference_resolver.py`, `backend/pipeline/synthesis/reference_validator.py` | `/ideas/:id` `EvidenceSummary` (resolved/unresolved counts); `remediation-banner.tsx` exists but NOT rendered | **PARTIAL** | test_pipeline/provenance | `proposal_references` on idea | Richer citation-audit component is dead code; only counts shown | HIGH |
| 17 | Generate BibTeX | VERIFIED — `BibTeXExporter` (`paper_to_bibtex`, `papers_to_bibtex`, `proposal_to_bibtex`) | `backend/pipeline/export/bibtex_exporter.py` | `/runs/:id` BibTeX button → `GET /api/export/bibtex/{run_id}` | **WORKING** | test_pipeline/export | `data/exports/` | Run-level only; no idea-level BibTeX in UI | HIGH |
| 18 | Evaluate evidence quality | PARTIAL — `FaithfulnessScorer` (`ClaimAssessment`) is closest analogue; wired into proposal synthesis when `evaluation_framework_enabled` | `backend/pipeline/evaluation/faithfulness_scorer.py`, `ensemble_review.py` | `/ideas/:id` mechanical_metrics + quality_checks per section | **PARTIAL** | test_evaluation | `quality_report.json` per run | No standalone evidence-quality endpoint | HIGH |
| 19 | Evaluate argument coherence | NONE | No module | NONE | **MISSING** | — | — | No backend, no UI | HIGH |
| 20 | Evaluate literature quality | PARTIAL — `RetrievalQualityScorer` scores retrieval, not end-to-end literature quality | `backend/pipeline/knowledge/retrieval_quality.py` | NONE | **NOT_EXPOSED** | test_ranking | — | Narrow (retrieval only); no UI | HIGH |
| 21 | Evaluate a paper / proposal | VERIFIED — `ProposalEvaluator` (7-dim), `EvaluationStage`, `QualityGate`, `PipelineEvaluator`, `AdversarialReviewer`, `mechanical_metrics` | `backend/pipeline/evaluation/proposal_evaluator.py`, `quality_gate.py`, `adversarial_reviewer.py` | `/ideas/:id` `ScoreReport`, `NoveltyReportView`, `FeasibilityReportView`, Metrics tab; `proposal-review-panel.tsx` exists but NOT rendered | **WORKING** | test_evaluation, test_quality_benchmarks | `quality_report.json` | Richer ensemble-review component is dead code | HIGH |
| 22 | External validation | NONE — only internal `verification/` (`CitationClaimAuditor`, `ReferenceVerifier`, `ProvenanceChecker`) | `backend/pipeline/verification/` (internal) | NONE — no `/validation` route | **NOT_EXPOSED** | test_pipeline/verification | — | Internal-only; no external reviewer step | HIGH |
| 23 | Export outputs | VERIFIED — `ExportService`, `MarkdownExporter`, `LatexExporter`, `BibTeXExporter`, `venue_templates` | `backend/pipeline/export/`, `backend/api/routes/{export,exports}.py` | Run-level: `/runs/:id` Markdown/LaTeX/BibTeX; Idea-level: `/ideas/:id` ExportDialog PDF + Markdown | **WORKING** | test_pipeline/export | `data/exports/` | Idea-level: PDF/Markdown only (no LaTeX/BibTeX); export route split between two files | HIGH |
| 24 | Resume failed runs | VERIFIED — `PipelineOrchestrator.resume()`, checkpoint save/load, stale-run watchdog | `backend/pipeline/orchestrator/_orchestrator.py:1107`, `backend/pipeline/persistence.py` | `/runs/:id` Resume button when `status==="failed"` → `POST /pipeline/resume/{id}` | **WORKING** | test_pipeline/persistence | `data/checkpoints/` | — | HIGH |
| 25 | Inspect progress | VERIFIED — `StageExecutor`, `RunEvent`, SSE | `backend/pipeline/orchestrator/stage_executor.py` | `/runs/:id` polling + stage timeline + tree search + ideas list; SSE via `usePipelineProgress` | **WORKING** | test_api/pipeline | `data/runs/run_*/log.jsonl` | — | HIGH |
| 26 | Use the current frontend end to end (research question → evaluated exported proposal) | VERIFIED | `pipeline-new.tsx` → `run-detail.tsx` → `idea-detail.tsx` → ExportDialog | All routes present | **PARTIAL** | frontend integration tests | — | **Cannot** produce a full *paper* via UI (only proposals); no NL research-question field; richer review components dead-coded | HIGH |
| 27 | Govern (approve / deny / audit) | VERIFIED — `/governance` pending/approve/deny; idea-scoped decisions + timeline | `backend/api/routes/governance.py`, `backend/api/routes/ideas/governance.py` | `/governance` queue (`ApprovalCard`); `/ideas/:id` `GovernancePanel` | **WORKING** | test_governance (4 files) | `data/governance_audit.jsonl` | — | HIGH |

## End-to-End Journey: "Research Question → Evaluated, Exported Proposal"

**Partially achievable via UI.** Exact gaps:

1. **Input gap:** `/pipeline/new` accepts `domain` (free text) + `search_queries` (keyword list, advanced panel). **No natural-language research-question field.** **No seed-paper/URL input.**
2. **Run + monitor:** WORKING (`/runs/:id`).
3. **Read proposal + scores:** WORKING (`/ideas/:id`).
4. **Refine:** WORKING (`POST /ideas/{id}/refine`, per-section fix).
5. **Govern:** WORKING (`GovernancePanel`).
6. **Export:** WORKING for proposal (PDF/Markdown idea-level; Markdown/LaTeX/BibTeX run-level).

**NOT achievable via UI:**
- Producing a **full research paper** (only proposals; paper-synthesis stage exists in pipeline but is not UI-exposed).
- BibTeX/LaTeX export of a **single idea** (run-level only).
- Viewing the richer `EvidencePanel` / `ProposalReviewPanel` / `RemediationBanner` (components exist but are not rendered by `idea-detail.tsx`).

## Dead-Code UI Components (exist, NOT rendered by any page) *[VERIFIED]*

| Component | Capability it would serve | Status |
|---|---|---|
| `frontend/src/components/ideas/evidence-panel.tsx` | Evidence/provenance card (per-reference resolution, match_method, confidence) | Dead code |
| `frontend/src/components/ideas/proposal-review-panel.tsx` | Ensemble review (methodology/novelty/clarity scores, strengths/weaknesses, risk flags) | Dead code |
| `frontend/src/components/ideas/remediation-banner.tsx` | Citation-audit consumption | Dead code |
| `frontend/src/components/ideas/quality-check-panel.tsx` | Quality checks | Dead code |
| `frontend/src/components/ideas/radar-chart.tsx` | Score radar | Dead code |
| `frontend/src/components/ideas/evaluation-card.tsx` | Evaluation card | Dead code |

> The live `idea-detail.tsx` instead renders inline lightweight versions: `EvidenceSummary` (counts only), `ScoreReport`, `NoveltyReportView`, `FeasibilityReportView`, `GovernancePanel`, `FixSectionButton`, `RevisionHistoryDrawer`, `FeedbackForm`, `CommentThread`, `ShareDialog`, `ExportDialog`.

---

*End of capability matrix. Generated from frontend + backend source inspection; no repository source or product artifact modified.*
