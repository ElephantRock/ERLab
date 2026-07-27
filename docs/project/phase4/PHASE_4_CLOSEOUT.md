# Phase 4 / WP-4B–4H + 4G Closeout — Evidence Grounding and Product Hardening

> **Tranche:** 4B, 4C, 4D, 4E, 4F, 4H, 4G complete. 4I (paid live validation)
> deferred — requires frozen provider/model/spend authorization.
> **No P1E artifact changed. No retrieval-ranking architecture changed.**
> **Canonical backend selector: zero failures** (corrected command, 4G).
> **No P1E artifact changed. No retrieval-ranking architecture changed.**

| Field | Value |
|---|---|
| **Baseline commit** | `bfe2e43bba7af90b4687db1997f6c5b5fa0ed2e3` |
| **Final commit** | `b91ea22` |
| **Branch** | `feat/quarantine-and-frontend-redesign` |
| **Commits in tranche** | 7 |
| **Files changed** | 25 (+3169 / -35) |
| **Working tree** | clean |

---

## Source-provenance loss boundary

Established in WP-4A (`docs/project/phase4/PHASE_4_SOURCE_PROVENANCE_TRACE.md`):

> The first demonstrated provenance-loss boundary is the non-persistence of the
> synthesis-time marker-to-source map. Embedding failure is not required to
> produce the missing-bibliography defect, although it may independently
> degrade retrieval, novelty checking, or source quality.

The Phase 3 framing ("missing bibliography downstream of ingestion failure") was
corrected: the synthesis path uses `ctx.all_papers` in memory, not the vector
store, so marker-map non-persistence is sufficient to explain the defect.

## Source identity and persistence path

DOI/arXiv/title/authors/year/venue/url are written by `persist_search_results`
to the `papers` table **before** `IngestionStage` runs (boundary 3, the governed
metadata boundary). This is unchanged by Phase 4. WP-4B added the missing piece:
the per-paper marker→source linkage (`paper_source_markers`), which connects
`[SOURCE-N]` markers in `paper_md` to the persistent `papers` rows.

## Embedding-failure behavior

Proven (not asserted) by `test_phase4_provenance_durability.py`: full
bibliographic identity persists through `persist_search_results` and survives
both embedding failure and application restart. The vector store path
(`vector_store.py:116-126`) never carried DOI/arXiv/authors/venue/url regardless
of success or failure, so embedding health is orthogonal to citation provenance.

## Citation-map persistence

New `paper_source_markers` table (migration 033):
`proposal_id, marker_index, marker, source_paper_id (nullable), mapping_status
(mapped|unmapped)`, `UNIQUE(proposal_id, marker_index)`. `PaperSynthesisStage.
build_source_map` freezes the ordered source list, scans the generated paper
for emitted markers, and records out-of-range markers as `unmapped` (identity
never guessed). `persist_proposals._persist_source_markers` resolves
`source_id → papers.id`, downgrading unresolvable entries to `unmapped`.

## Bibliography and export behavior

All four consumers read the **same** persisted map via
`backend/pipeline/provenance/citation_map.py`:
- **Markdown / LaTeX** append a references section rendered from the map.
- **Per-idea BibTeX** emits `@article` entries for mapped external sources.
- **Per-run BibTeX** emits the run's cited external sources (deduplicated by
  `source_paper_id`) — fixes the Phase 3 "only self-citations" defect where
  `export_run_bibtex` fabricated `Paper(source='elephant_rock')` per idea and
  never read the `papers` table.

## Trust & Sources behavior

The review payload now exposes `citation_markers` from the same persisted map,
so the UI shows the authoritative source list that exports use. The legacy
`sources` field (keyed on `source_ref_hash` for human-review decisions) is
retained for backward compatibility.

## Provenance evaluation gate

`PaperSynthesisStage.provenance_precondition` runs before the evaluator can
report an unqualified positive state. A paper citing `[SOURCE-N]` markers with
no persisted map, or with all markers unmapped, fails the precondition. The
evaluation is recorded `status="blocked"` with a concrete reason; the paper
artifact remains accessible (`paper.status` is separate from `paper_evaluation`).

## Scope-drift findings

`scope_checker.classify_scope_alignment` compares the frozen research intent
against the paper's title + abstract via vocabulary overlap (title similarity
not used alone). Detects the Phase 3 Q-Sym pattern (neuro-symbolic
verifiability → quantization): zero vocabulary overlap → `off_scope` → blocks a
positive evaluation. Missing research intent → `unavailable`, not inferred.

## Conclusion-overreach findings

`conclusion_checker.classify_conclusion_support` detects strong-claim language
("demonstrates", "proves", "significantly improves", "validates") + causal
conclusions without reported empirical results — the Phase 3 design+projection
pattern (3/6 papers). An `overstated` finding blocks a positive evaluation.

## Controlled remediation result (WP-4H)

`test_phase4_end_to_end.py` (4 tests, all green) proves the full source-identity
path end-to-end with **no external provider**:
1. durable metadata survives → exports cite real sources;
2. Trust & Sources exposes the same map;
3. provenance gate blocks false confidence on a paper lacking provenance;
4. source identity + marker map survive an application restart;
5. an unmapped marker is reported explicitly, never silently dropped.

## Frozen live rerun matrix

**Not executed.** WP-4I deferred per user direction; requires frozen
provider/model/spend authorization.

## Persistence results

Proven offline in the controlled integration: source identity, marker map, and
export hashes are stable across a simulated restart. (Live post-restart
verification is part of the deferred 4I.)

## Independent citation / claim-support findings

**Not executed.** These audit the output of live runs (4I). The controlled 4H
proves the *path* is auditable: every marker has a mapped or explicit unmapped
state, so an independent audit against future live output can resolve every
`[SOURCE-N]` to a real `Paper` row.

## Phase 3 vs Phase 4 comparison

| Phase 3 defect | Phase 4 remediation |
|---|---|
| Missing bibliography (6/6 papers) | Marker map persisted + rendered into MD/LaTeX/BibTeX |
| Unresolvable markers | Explicit `unmapped` state, never dropped |
| False-ready evaluation (6/6) | Provenance gate → `status="blocked"` |
| Scope drift (1/6, Q-Sym) | `scope_checker` detects zero-overlap drift |
| Conclusion overreach (3/6) | `conclusion_checker` detects strong-claim-no-results |
| BibTeX only self-citations | Per-run BibTeX emits cited external sources |
| Trust & Sources wrong list | Exposes same map exports use |

## Architecture result

**41 passed, 0 failed.**

## Ranking result

**253 passed, 3 skipped.**

## Frontend result

**988 tests passed, build clean, lint/budgets hold** (matches Phase 3 baseline;
no frontend files changed in this tranche).

## Full backend selector result

**4G closed the selector to zero failures.** The history:

```
OLD command (INVALID — retired in 4G):
  pytest -p no:asyncio -m "not slow and not integration"
  138 failed, 4643 passed, 47 skipped   (baseline at 4B–4H tranche start)
  141 failed, 4688 passed, 47 skipped   (after 4B–4H, before 4G)
  Real pytest exit code: 1
  Status (then): FAILING

CORRECTED command (4G):
  pytest -m "not slow and not integration"
  4830 passed, 47 skipped, 37 deselected, 327 warnings
  Real pytest exit code: 0
  Status: PASS — zero failures
```

### Correction of the 4B–4H tranche report

The 4B–4H closeout attributed the +3 delta (138 → 141) to "test-isolation
nondeterminism in pre-existing failure buckets." **That attribution was wrong.**
The 4G set comparison (baseline-138 vs checkpoint-141) proved the 3 new failures
were a real 4C signature-contract regression in `test_phase3_paper_synthesis_timeout.py`
(fixed in `d5c112a`). Same-cluster membership and isolation-passing are evidence
for the nondeterminism hypothesis, not proof — the set comparison was required to
falsify it.

### What the 138 "baseline" failures actually were

The 4G decisive experiment proved the 138 were **not** test-isolation pollution,
not global-state leaks, not production defects. They were the `-p no:asyncio`
flag disabling the asyncio plugin required by ~138 legitimate async tests
(canonical = 141 failed; default mode = 3 failed). The flag was a workaround for
GOTCHA-001 (trio-mode failures, BATCH-75 era); trio risk now verified gone. The
corrected command retired the flag. See `PHASE_4_TEST_ISOLATION_REPORT.md`.

### Regressions caught and fixed across 4B–4G

Four regressions introduced during 4C/4H were caught by these gates,
root-caused, and fixed in-commit before completion:
- batch153 `source_ids` NameError (`b91ea22`)
- batch174 MagicMock regex TypeError (`b91ea22`)
- 6 async integration tests failed under `-p no:asyncio` (`855272a`)
- 3 timeout-test signature mocks broken by the `source_ids` arg (`d5c112a`)

Plus the 2 genuine pre-existing defects fixed in 4G:
- stale frontend-route assertion (`1a41c17`)
- alembic `fileConfig` disabling pre-existing loggers (`1a41c17`)

## Production-code changes

- `backend/db/models.py` — `PaperSourceMarker` model.
- `backend/db/crud.py` — `add_source_marker`, `replace_source_markers`,
  `get_source_markers_for_proposal`.
- `alembic/versions/033_paper_source_markers.py` — migration.
- `backend/pipeline/stages.py` — `build_source_map`, `provenance_precondition`,
  `_classify_scope`, `_classify_conclusion`, `_evaluate_paper` gate wiring,
  `source_ids` threading.
- `backend/pipeline/synthesis/paper_synthesizer.py` — `source_map` field.
- `backend/pipeline/persistence.py` — `_extract_paper_artifact` threading,
  `_persist_source_markers`, `persist_proposals` marker persistence.
- `backend/pipeline/provenance/citation_map.py` — **new**: reader + renderers.
- `backend/pipeline/evaluation/provenance_gate.py` — **new**: result dataclass.
- `backend/pipeline/evaluation/scope_checker.py` — **new**: 4E.
- `backend/pipeline/evaluation/conclusion_checker.py` — **new**: 4F.
- `backend/api/routes/paper_export.py` — MD/LaTeX/BibTeX consume the map.
- `backend/api/routes/exports.py` — per-run BibTeX rewired.
- `backend/api/routes/review.py` — `citation_markers` from the map.

4G additions (test isolation):
- `alembic/env.py` — `fileConfig(..., disable_existing_loggers=False)` (real
  global-state defect repair).
- `alembic.ini` — `disable_existing_loggers = False` documents the intent.
- `Makefile`, `.github/workflows/{ci,nightly}.yml` — corrected canonical command
  (retired the invalid `-p no:asyncio` flag).
- `backend/tests/test_pipeline/test_batch173_verification.py` — subprocess
  invocation corrected.
- `backend/tests/test_pipeline/test_batch171_alpha.py` — stale frontend-route
  assertion updated to the current AppRoutes.tsx contract.
- `backend/tests/test_pipeline/test_phase4_logging_isolation.py` — **new**:
  focused regression for the alembic-logger-disabling defect.
- `docs/project/ERLAB_CURRENT_STATE_REPORT.md`, `erlab_current_state_inventory.json`
  — current-state docs updated.

Paper-synthesis prompts, retrieval, and ranking are **unchanged**.

## Known limitations

1. **Full backend selector: PASS (zero failures)** after 4G corrected the
   canonical command and repaired the alembic logger-disabling defect. The
   prior "138 baseline failures" were the invalid `-p no:asyncio` flag, not
   real defects. See `PHASE_4_TEST_ISOLATION_REPORT.md`.
2. **Live validation not run** — WP-4I deferred; requires provider/model/spend
   authorization. The controlled 4H proves the path offline.
3. **Independent citation/claim-support audits not run** — these audit live
   output (4I). The path is now auditable: every marker resolves.
4. **Scope/conclusion checkers are deterministic heuristics**, not LLM judges.
   They detect the enumerated indicator patterns; they do not perform semantic
   claim analysis. This matches the plan's "use the existing evaluation
   architecture only" and "no external provider required for 4H" constraints.
5. **`source_id` precedence is inconsistent across providers** (bare arXiv,
   prefixed PubMed/CrossRef, title-fragment fallback). The marker table links
   via `source_paper_id` (DB PK), so provenance doesn't depend on a normalized
   key, but cross-source dedup at ingest remains a separate concern.

## P1E artifacts changed = 0

## Retrieval ranking architecture changed = 0

## Working tree status

**clean** at closeout.

---

*End of Phase 4 tranche (4B–4H + 4G). 4I (paid live validation) deferred — requires frozen provider/model/spend authorization.*
