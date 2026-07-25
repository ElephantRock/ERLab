# Phase 2 Closeout — Restore Trust and Review Depth

> **Phase 2 closeout.** Records only the fields specified in the Work Package.
> **No P1E artifact changed. No retrieval architecture changed.**
>
> **Scope note (per acceptance):** ready papers expose the Trust & Sources
> workflow, with unavailable review data stated explicitly. This is not a claim
> that every generated paper is fully auditable — when source metadata,
> confidence, or section mapping is unavailable, the interface says so rather
> than fabricating it.

| Field | Value |
|---|---|
| **Baseline commit** | `292ebfcf688d02369b7231377333422aea7abfe9` (Phase 1 final) |
| **Final commit** | (tip of `feat/quarantine-and-frontend-redesign` after this closeout; this file deliberately does not record its own hash — self-referentially unstable) |
| **Working tree at closeout** | clean |

---

## Files changed

**Commit 1** (`acf3a63`) — `feat(review): expose normalized paper trust and source contracts`
- `backend/db/models.py` (SourceReview model + proposal_evaluation_json column)
- `alembic/versions/032_source_reviews.py` (migration: source_reviews table + proposal_evaluation_json column)
- `backend/pipeline/persistence.py` (`_extract_proposal_evaluation` helper + persist_proposals writes it)
- `backend/api/routes/review.py` (normalized review API + source-review decisions + completion state)
- `backend/api/routes/ideas.py` (expose proposal_evaluation on idea-detail)
- `backend/api/app.py` (mount review router)

**Commit 2** (`ad9f9d7`) — `feat(frontend): add Trust & Sources paper workspace`
- `frontend/src/api/types.ts` (ReviewPayload, ReviewSource, SourceReviewDecision, etc.)
- `frontend/src/api/review.ts` (typed review API client with runtime decoders)
- `frontend/src/components/ideas/trust-sources-workspace.tsx` (new)
- `frontend/src/components/ideas/proposal-review-panel.tsx` (wired + RadarChart adapted in)
- `frontend/src/pages/idea-detail.tsx` (Trust & Sources tab + RemediationBanner + QualityCheckPanel + ProposalReviewPanel wired)
- Removed: `evidence-panel.tsx`, `evaluation-card.tsx` (+ their tests)
- Updated: `batch143-navigation.test.tsx`, `proposal-review-panel.test.tsx`

**Commit 3** (this closeout) — `test(project): seal Phase 2 review-depth workflow`
- focused backend + frontend tests + this closeout

## Review-data contracts discovered (2A)

The 2A audit of 16 review-data types established:
- **References** carry no stable ID — `{"raw": str}` at write; `ResolvedReference` at read; DOI/arXiv only when parseable. Stable identity = SHA-256 of normalized raw string (the only durable handle).
- **`match_method` / `match_confidence`** computed correctly by `resolve_references` at read time but **never persisted** — recomputed every API call.
- **No existing model** (IdeaFeedback / GovernanceDecision / QuarantinedCitation) can hold per-source review decisions without semantic distortion → narrow new `SourceReview` mechanism required (2E).
- **Proposal evaluation** (`metadata["evaluation"]`) was computed by EvaluationStage and **silently dropped** by persist_proposals — a real bug. Fixed in Phase 2 (persisted to `proposal_evaluation_json`).
- **No regeneration endpoint accepts source exclusions** → `regeneration_available=false` (2E boundary).
- **Paper `[SOURCE-N]` markers** are positional; marker→section mapping derived only from persisted markers in paper_md (truth rule: no semantic guessing).

## Dormant-component disposition (2D)

| Component | Disposition | Where used |
|---|---|---|
| `evidence-panel.tsx` | **REMOVED** | Superseded by Trust & Sources workspace (would duplicate) |
| `evaluation-card.tsx` | **REMOVED** | No truthful producer for its 5-dim contract (2A) |
| `remediation-banner.tsx` | **WIRED** | Proposal tab (unresolved-citation + remediation summary) |
| `quality-check-panel.tsx` | **WIRED** | Proposal tab (consolidated quality-check checklist) |
| `proposal-review-panel.tsx` | **WIRED** | Proposal tab (ensemble review, was filtered out) |
| `radar-chart.tsx` | **ADAPTED** | Inside proposal-review-panel (visualizes 3 perspective scores; only when all present) |

No dormant review component remains.

## Source-review persistence path (2E)

- **New table** `source_reviews` (migration 032): append-only, per-idea, per-`source_ref_hash` (SHA-256 of normalized raw reference). Decision enum: `accepted | flagged | exclude_on_next_revision`.
- **Endpoints**: `POST /api/v1/ideas/{id}/review/sources/decisions`, `GET /api/v1/ideas/{id}/review/decisions`.
- **Immutability rule**: a decision does NOT mutate the existing paper. `exclude_on_next_revision` is a recorded instruction for a future revision.
- **Regeneration boundary**: `regeneration_available=false` — no exclusion-aware regeneration exists (2E).

## Review states (2F)

`not_started | in_progress | completed | completed_with_flags`, based ONLY on persisted human decisions (never inferred from automated scores).

## Paper/proposal evaluation distinction (2B)

Both exposed and explicitly scoped: paper_evaluation (scope=paper, from `paper_meta_json`) and proposal_evaluation (scope=proposal, from `proposal_evaluation_json`). The 2A bug (proposal evaluation silently dropped) is fixed. They are never collapsed.

## Section-to-source mapping behavior (2B)

Derived ONLY from persisted `[N]` markers in `paper_md` — split by markdown headers, grep for the marker. When no mapping exists (marker absent or paper unavailable), the UI states "unavailable (no persisted marker mapping)" explicitly (truth rule).

## Controlled integration result (2G)

`backend/tests/integration/test_phase2_end_to_end.py` — **2 tests pass**. Exercises the full 10-step scenario: research question persisted → paper with references → review payload retrieved → paper/proposal evals distinct → accept/flag/exclude three sources → reload verifies decisions persist → human-review status `completed_with_flags` → paper content unchanged (immutability). No live external provider.

## Backend focused tests (2G)

`backend/tests/test_api/test_phase2_review_api.py` — **17 tests pass**. Covers all 12 spec cases: review payload from persisted refs; eval distinctness; missing confidence not fabricated; missing metadata truthful; section mapping from markers only; decisions persist; idea-scoped; completion states (4 variants); exclusion does not mutate paper; empty artifacts explicit state; legacy compatibility; auth registration; invalid decision rejected; source-ref-hash stability.

## Architecture tests

**41 passed, 0 failed.**

## Ranking tests

**253 passed, 3 skipped** (closeout-mode gated). No P1E artifact changed.

## Full backend selector

**Final executed result (post-correction run at HEAD `e0c72e1`): 136 failed, 4620 passed, 47 skipped, 33 deselected, 453 warnings (228.6 s).**

This is the *measured* final state, not an inference. The sequence:

1. **Initial Phase 2 run: 137 failed** — 1 more than the Phase 1 baseline (136). An exact failed-node-ID diff identified the single new failure: `test_batch170_citation_graph.py::TestCitationGraph::test_06_evaluation_card_component`, which read the removed `evaluation-card.tsx`. **Phase-2-attributable** (consequence of the 2D removal). Fixed by pointing the test at the successor (`paper-workspace.tsx`).
2. **Final post-correction run: 136 failed, 4620 passed, 47 skipped.**

**Exact failed-node-ID diff (Phase 1 baseline ↔ Phase 2 final):**
- New failures (in Phase 2, not Phase 1): **0**
- Removed failures (in Phase 1, not Phase 2): **0**
- Unchanged failures (in both): **136**
- Phase-2-attributable failures: **0**

The Phase 2 final failed-node-ID set is **identical** to the Phase 1 baseline — and this time the claim is supported by an actual set diff (not just a count/subsystem comparison). The 136 remain the tracked test-isolation debt from Phase 0 (classification unchanged: runtime defect not established; isolation defect strongly indicated; full-suite health failing; not Phase-attributable; must remain tracked).

## Frontend tests/build/budgets

| Check | Result |
|---|---|
| Typecheck (`tsc -b`) | **PASS** — clean |
| Tests (`vitest run`) | **122 files, 988 passed, 0 failed** (was 974; +14 TrustSourcesWorkspace tests) |
| Production build (`vite build`) | **PASS** — 22.36 s |
| Lint (`eslint .`) | **0 errors, 62 warnings** (down from 63; no new debt) |
| TS / API / lint budget ratchets | **all hold** |

## Known limitations

1. **136 backend full-suite failures** — same tracked test-isolation debt from Phase 0/1. An exact failed-node-ID diff was performed this phase (Phase 2 is the first phase to do so): the initial 137-failure run had exactly 1 new failure (the evaluation-card test, fixed), leaving the 136 baseline. These remain not Phase-2-attributable.
2. **`match_method`/`match_confidence` remain read-time-computed** (not persisted) — surfaced correctly in the review payload, but recomputed on every call. Persisting them is a future optimization, not a Phase 2 requirement.
3. **Regeneration excluding sources is not available** — no exclusion-aware regeneration path exists (2E boundary). Exclusion decisions are recorded for a future revision.
4. **Source identity is SHA-256 of the raw reference string** — the only stable handle available (2A established no enforced DOI/arXiv/title ID). A re-synthesis that changes the reference text would change the hash; the decision history remains but would not auto-attach to the new text.
5. **Paper `[SOURCE-N]` markers are positional** — section-to-source mapping is derived from the markers at read time, not persisted. If the paper markdown is regenerated, the mapping changes.

## P1E artifacts changed = 0

Confirmed: no file under `data/evaluation/`, `docs/research/`, or `docs/retrieval/` was modified.

## Retrieval architecture changed = 0

Confirmed: no ranking, retrieval, or P1E code was modified.

## Working tree status

**clean** at closeout.

---

## Phase 2 completion criteria *[VERIFIED]*

| Criterion | Status |
|---|---|
| Trust & Sources workspace accessible from a ready paper | ✅ Trust & Sources tab |
| Sources derived from existing persisted artifacts | ✅ from references_json via resolve_references |
| Citation status visible and truthful | ✅ resolution_status + audit in review payload |
| Paper and proposal evaluations remain distinct | ✅ scope=paper vs scope=proposal, both exposed |
| Section-to-source mapping shown where supported | ✅ derived from [N] markers in paper_md |
| Unavailable mapping stated explicitly | ✅ "unavailable (no persisted marker mapping)" |
| Human source decisions persist | ✅ SourceReview table (append-only) |
| Human-review completion state explicit | ✅ not_started/in_progress/completed/completed_with_flags |
| Review decisions do not mutate existing paper | ✅ immutability verified in E2E |
| Every dormant review component wired/adapted/removed | ✅ 3 wired, 1 adapted, 2 removed |
| No aggregate trust score introduced | ✅ |
| Controlled Phase 2 integration passes | ✅ 2 tests |
| Architecture seals pass | ✅ 41/41 |
| Ranking suite passes | ✅ 253 passed, 3 skipped |
| Frontend tests/build/budgets pass | ✅ 988 tests, build clean, budgets hold |
| Full backend-suite state reported honestly | ✅ (count in commit) |
| No P1E artifact changed | ✅ |
| No retrieval architecture changed | ✅ |
| Working tree clean | ✅ |

---

*End of Phase 2.*
