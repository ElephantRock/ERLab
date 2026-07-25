# ERLab Open, Blocked, and Deferred Decisions

> **Companion to** `ERLAB_CURRENT_STATE_REPORT.md` Part 10.
> **Status enum:** COMPLETE, OPERATIONAL, OPEN, BLOCKED, DEFERRED, SUPERSEDED, UNKNOWN.
> **Do not invent blockers.** Every blocker below cites a VERIFIED artifact or commit.

## Consolidated Table

| # | Item | Status | Exact blocker (with evidence) | Blocks product? | Blocks research R&D only? | Smallest next action | Dependencies |
|---|---|---|---|---|---|---|---|
| 1 | **P1 — ranking quality objective** | OPEN | No candidate policy has passed the frozen gate (P1B best +0.0065 ≪ 0.03 threshold, all FAIL); P1D Outcome B (no significant improvement); P1E.0 Outcome M (inconclusive) | Indirect (research quality) | YES | Decide retrieval architecture (run P1E.3 once P1E.2 unblocked, or adopt a new approach) | P1E.2, P1E.3 |
| 2 | **P1E.2 — held-out adjudication** | BLOCKED | Custody prerequisites: independent-custody requirement not met (current custodian resides within governed environment; `p1e1_adjudication_provenance.json` flags this as a prerequisite, not a failure) | NO | YES | Establish independent custody; adjudicate the 22 held-out cases | Independent custody infrastructure |
| 3 | **P1E.3 — frozen policy comparison** | BLOCKED | Depends on P1E.2 (held-out must be adjudicated first); `p1e3_policy_evaluation: "not_performed"` | NO | YES | Unblock P1E.2; run measured paired-policy MDE on extended benchmark | P1E.2 |
| 4 | **P2** | BLOCKED | P1 unresolved — P2 was predicated on a passing P1 policy | NO | YES | Resolve P1 | P1 |
| 5 | **Interface completion** | OPEN | (a) No NL research-question input; (b) no full-paper UI; (c) 6 dead-code rich UI components; (d) P0.5 architecture-seal regression; (e) idea-level export format gap (no LaTeX/BibTeX) | **YES** | NO | Add research-question field; repair P0.5 seal; decide wire-or-remove for dead components | None (independent) |
| 6 | **End-to-end paper workflow** | OPEN | Full paper generation (`PaperSynthesizer`) exists in pipeline but is NOT UI-exposed | **YES** | NO | Expose paper-vs-proposal toggle in `/pipeline/new` | None |
| 7 | **Comparison with old papers** | DEFERRED | 3 historical full papers deleted in Phase 0 wipe (`e2c0171`); recoverable via `git show e2c0171~1:<path>` but no current comparison artifact exists | NO | NO | Recover via git if comparison needed | None |
| 8 | **Retrieval architecture decision** | OPEN | P1E.0 Outcome M inconclusive — neither saturation nor architectural signal complete; P1E.1 evaluation not run | Indirect | YES | Run P1E.3 once P1E.2 unblocked | P1E.2, P1E.3 |
| 9 | **Held-out adjudication** | BLOCKED | (= P1E.2) Custody prerequisites | NO | YES | (= P1E.2) | Independent custody |
| 10 | **Product release readiness** | OPEN | E2E paper workflow incomplete; architecture-seal regression; benchmark lineage unresolved | **YES** | NO | Close interface gaps (#5, #6); repair seal (#11) | #5, #6, #11 |
| 11 | **P1D.2 dual independent review** | BLOCKED | 81 provisional single-pass judgments by one author (`eligible_for_scoring: false`); protocol explicitly NOT sealed ("actual review requires independent people or independently governed reviewers") | NO | YES | Recruit independent reviewers; execute blinded packages A and B | Independent reviewers |
| 12 | **P0.5 architecture-seal regression** | OPEN | `backend/ranking/generate_embedding_snapshot.py:62` reads `os.environ.get("P1C_SNAPSHOT_TAG", ...)` directly, violating `backend/tests/architecture/test_p0_5_seal.py::test_no_direct_os_environ_in_production` | NO (governance) | NO | Route `P1C_SNAPSHOT_TAG` through `Settings` | None |
| 13 | **Stale `benchmarks/latest.json`** | OPEN | References 65 deleted pre-wipe runs (2026-05-13); `db_id`s no longer exist | NO (governance) | NO | Delete or supersede with current benchmark lineage | None |
| 14 | **Independent custody infrastructure** | BLOCKED | P1E.2 requires a custodian outside the governed environment; current custodian role resides within it | NO | YES | Define and stand up independent custody boundary | Organizational decision |
| 15 | **Current full-suite test baseline** | OPEN | `.pytest_cache/v/cache/lastfailed` (2026-07-25 03:08) lists 88 failing node IDs but is STALE — DB migration tests it lists now pass; only the architecture-seal failure (#12) is VERIFIED current | NO (governance) | NO | Run a fresh full pytest suite to establish current green/failing baseline | None |
| 16 | **Dead-code UI components** | OPEN | `evidence-panel.tsx`, `proposal-review-panel.tsx`, `remediation-banner.tsx`, `quality-check-panel.tsx`, `radar-chart.tsx`, `evaluation-card.tsx` exist but are not imported by any page | **YES** (product depth) | NO | Wire-or-remove decision per component | None |

## Items NOT Listed (Already Closed)

Phase 0 wipe, P0.3, P0.4, P0.5 (program — the *seal* regression in #12 is separate), P1 (infra), P1B, P1C, P1D, P1E.0, P1E.1 (corpus + cal/dev), F0, F1.1, F1.2, F1.3, F1.4, F1.5, F1.6, F1.7. These are COMPLETE per their closeout artifacts and should not be reopened. Re-evaluation of any frozen artifact requires a new versioned experiment per the integrity accounting of the relevant closeout.

## Cross-Cutting Blockers

The **P1 ranking chain** (#1, #2, #3, #4, #8, #9, #14) is the dominant research-R&D blocker. It does not directly block the user-facing product (which can still produce evaluated proposals), but it blocks any claim of improved retrieval quality.

The **interface/product blockers** (#5, #6, #10, #16) are independent of the P1 chain and independently block product release readiness.

The **governance blockers** (#12, #13, #15) are low-cost, independent, and do not block either track.

---

*End of open decisions. No blocker invented; every entry cites a VERIFIED artifact, commit, or test result. No repository source or product artifact modified.*
