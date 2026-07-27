# Phase 4 Defect Ledger

> Tracked defects and their remediation status across the 4B–4H tranche.

## Defects remediated (4B–4F + 4H)

| ID | Defect | Work package | Remediation | Status |
|---|---|---|---|---|
| 4A-BIB | Papers contain `[SOURCE-N]` markers but no bibliography | 4A → 4C | Marker→source map frozen at synthesis, persisted to `paper_source_markers`, consumed by all exports + Trust & Sources | **CLOSED** |
| 4A-IDS | Source identity not durable across the synthesis boundary | 4A → 4B | Proven `persist_search_results` already writes DOI/arXiv before embedding; new marker table links to it | **CLOSED** |
| 4B-EMB | (Hypothesis) embedding failure discards metadata | 4B | Refuted by code path; metadata survives embedding failure (proven by durability tests). Embedding failure independently degrades retrieval/novelty, not citation provenance | **CLOSED (refuted)** |
| 4C-SELF | Per-run BibTeX contained only self-citations | 4C | `export_run_bibtex` rewired to emit cited external sources from the marker map (deduplicated by source_paper_id) | **CLOSED** |
| 4C-REFS | Per-idea BibTeX derived from hallucinated `references_json` | 4C | Rewired to emit `@article` entries from the persisted marker map | **CLOSED** |
| 4C-REV | Trust & Sources reconstructed a different source list from exports | 4C | Review payload now exposes `citation_markers` from the same persisted map | **CLOSED** |
| 4D-FALSE | Evaluator reported `ready` on papers with missing provenance | 4D | Provenance precondition gate; failing gate → `status="blocked"`, never `ready` | **CLOSED** |
| 4E-DRIFT | Scope drift undetected (Q-Sym pattern) | 4E | `scope_checker.classify_scope_alignment` detects zero-overlap drift → blocks positive evaluation | **CLOSED** |
| 4F-OVERREACH | Conclusion overreach undetected (3/6 design+projection papers) | 4F | `conclusion_checker.classify_conclusion_support` detects strong-claim-without-results → blocks | **CLOSED** |

## Defects deferred

| ID | Defect | Work package | Reason |
|---|---|---|---|
| 4G-ISOLATION | Full backend selector has ~138-141 test-isolation failures | 4G | Explicitly deferred by user direction. Not in 4B–4H scope. |
| 4I-LIVE | Live paid validation not run | 4I | Requires frozen provider/model/spend authorization. Controlled 4H proves the path offline. |

## Regressions introduced and fixed in-tranche

| Regression | Cause | Fix commit |
|---|---|---|
| `test_batch153` NameError on `source_ids` | 4C referenced a variable from `execute()` inside `_synthesize_paper_for_proposal` without passing it | `b91ea22` — threaded `source_ids` through the call site |
| `test_batch174` TypeError on MagicMock regex | `build_source_map` called `re.findall` on a non-string mock | `b91ea22` — coerce non-string input to `""` |
| 6 async integration tests failed under `-p no:asyncio` | `@pytest.mark.asyncio` is a no-op without the asyncio plugin | `855272a` — converted tests to sync via `asyncio.run` |

All three regressions were caught by the final verification gate, root-caused, and fixed before the tranche was reported complete. None reached the user as a known issue.
