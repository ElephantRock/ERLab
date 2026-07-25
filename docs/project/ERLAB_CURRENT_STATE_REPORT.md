# ERLab Current-State Report

> **Reporting package.** This is a reporting document only. It does not propose
> a roadmap, reopen closed phases, or modify any artifact.
>
> **Source of truth:** repository at `C:\Next-Era\Elephant-Rock-Research-Lab`,
> branch `feat/quarantine-and-frontend-redesign`, HEAD `cea3ea16378ef7bbf7848cc31febf93af2478841` (2026-07-25).
>
> **Evidence classification** (used throughout):
> - **VERIFIED** — proven by repository content, committed artifacts, tests, or git history in this session.
> - **REPORTED** — stated in existing documentation, not independently re-proven from current state.
> - **INFERRED** — reasonable interpretation of verified evidence.
> - **UNKNOWN** — evidence absent or contradictory.
>
> **Status enum** (per the task contract): COMPLETE, OPERATIONAL, OPEN, BLOCKED, DEFERRED, SUPERSEDED, UNKNOWN.

---

## Part 1 — Repository Baseline  *[VERIFIED]*

| Field | Value |
|---|---|
| Repository root | `C:\Next-Era\Elephant-Rock-Research-Lab` |
| Current branch | `feat/quarantine-and-frontend-redesign` |
| HEAD | `cea3ea16378ef7bbf7848cc31febf93af2478841` |
| Parent | `a6c35e670f67a0331cc71074caf229e52b02b9c2` |
| Working-tree status | **clean** (no uncommitted changes at start of this task) |
| First commit (root) | `a7a9379dd42276e2ee5bbb570b4f3e7cbc9669e8` |
| Main branch (PR target) | `master` |

### Top-level packages and applications *[VERIFIED]*

| Package | Purpose | Entry point |
|---|---|---|
| `backend/` | Python backend (FastAPI + pipeline + CLI) | `backend/api/app.py`, `backend/cli/main.py`, `backend/pipeline/orchestrator/_orchestrator.py` |
| `frontend/` | React + TypeScript SPA | `frontend/src/main.tsx` → `App.tsx` → `AppRoutes.tsx` |
| `coordinator/` | Reviewer identity maps (P1D.2) | `coordinator/p1d2_review_identity_map.json` |
| `scripts/` | One-off builders/evaluators (P1D/P1E/P1E.1) | `scripts/p1e_benchmark_discrimination_audit.py`, `scripts/p1e1_*.py` |
| `alembic/` | DB migrations (versions through 030+) | `alembic.ini` |
| `docs/` | Documentation + sealed artifacts | `docs/research/`, `docs/retrieval/`, `docs/frontend/`, `docs/f0_frontend_recovery/` |
| `data/` | Runtime data, DBs, evaluation artifacts | `data/elephant_rock.db`, `data/evaluation/`, `data/runs/`, `data/exports/` |
| `benchmarks/` | Legacy benchmark snapshots | `benchmarks/latest.json` (STALE — see Part 2) |
| `exports/` | Top-level export dir | **EMPTY** |
| `reports/` | Generated reports | `reports/retrieval/` |

### Current frontend entry points *[VERIFIED]*

`frontend/src/main.tsx` → `App.tsx` → `AppRoutes.tsx` (production route registry, also imported by integration tests).

**20 routes** (`frontend/src/AppRoutes.tsx:78-99`):
`/`, `/pipeline/new`, `/runs/:id`, `/ideas`, `/ideas/:id`, `/gaps`, `/gaps/:id`, `/knowledge`, `/settings`, `/costs`, `/memory`, `/governance`, `/traces`, `/sessions`, `/literature`, `/knowledge-graph`, `/autonomous`, `/plugins`, `/ops`, plus `*` → redirect to `/`.

### Backend / research-pipeline entry points *[VERIFIED]*

| Entry | Path | What it does |
|---|---|---|
| Pipeline orchestrator | `backend/pipeline/orchestrator/_orchestrator.py` (`PipelineOrchestrator.run/resume/autonomous_cycle`) | 16-stage research pipeline |
| FastAPI app | `backend/api/app.py` | ~30 route groups under `/api/v1/...` |
| CLI | `backend/cli/main.py` (`erock` Typer app) | `search`, `ingest`, `generate --resume`, `novelty-check`, `feasibility-score`, `status`, `autonomous`, `ideas`, `runs`, `gaps`, `knowledge`, plus sub-apps `setup/dev/db/research/capability/config` |
| E2E harness | `run_e2e_pipeline.py` (repo root) | Runs `deep_research` strategy on a fixed domain; not part of pytest |

### Primary CLI / API execution paths *[VERIFIED]*

- **Launch a run (CLI):** `erock generate --domain … [--queries …] [--resume <run_id>] [--export]`
- **Launch a run (API):** `POST /api/v1/pipeline/run` → `PipelineOrchestrator.run`
- **Resume:** `POST /api/v1/pipeline/resume/{run_id}` or `erock generate --resume <run_id>`
- **Progress (SSE):** `GET /api/v1/pipeline/runs/{id}/progress`
- **Strategies:** `deep_research` (16 stages), `fast_scan` (6), `academic_proposal` (16), `literature_review` (4) — defined in `backend/pipeline/strategies/presets.py` and `backend/pipeline/dag/pipeline.yaml`

### Test-suite structure *[VERIFIED — counted this session]*

- **463 Python test files** under `backend/tests/` → **1180 test functions** (4822 collected node IDs with parametrize expansion)
- **122 frontend test files** under `frontend/src/` → ~1031 `it(`/`test(` calls
- 30 Python skip directives (all environment-gated); 0 frontend skips; 0 `xfail`
- Major subdirs: `test_pipeline` (247 files), `test_api` (45), `test_ranking` (13), `architecture` (5 invariant seals)
- pytest config (`pyproject.toml`): `testpaths=["backend/tests"]`, markers `slow/integration/live/requires_lmstudio/flaky`, coverage `fail_under=72`, CI runs `pytest -p no:asyncio -m "not slow and not integration"`
- See Part 8 for current green/failing state.

### Generated-artifact locations *[VERIFIED]*

| Location | Contents |
|---|---|
| `data/runs/run_*/` | 24 run directories (2026-06-16 through 2026-07-15) with `brief.json`, `plan.json`, `log.jsonl`, `quality_report.json`, `proposals/*.md` |
| `data/exports/` | Re-exported proposals under sanitized filenames + 1 empty stub |
| `data/evaluation/` | 16 P1E/P1E.1 benchmark JSON artifacts |
| `docs/research/` | P1E.0/P1E.1 markdown + 4 protocol versions + JSON mirror |
| `docs/retrieval/` | P1D closeout, deployment config, diagnostic seeds, reviewer packages |
| `docs/p1b_snapshot/`, `docs/p1b_gate1/`, `docs/p1b_gate2/` | Frozen ranking snapshots + blind-adjudication packages |
| `data/checkpoints/` | ~33 post-wipe checkpoint JSONs |
| `benchmarks/latest.json` | **STALE** — references 65 deleted pre-wipe runs (see Part 2) |

### Documentation structure *[VERIFIED]*

`docs/` subdirectories: `aiv`, `endpoints`, `examples`, `f0_frontend_recovery`, `frontend`, `migration`, `p1b_gate1`, `p1b_gate2`, `p1b_snapshot`, `product_validation`, `reference-patterns`, `research`, `retrieval`, `project/` (this report).

Top-level product/philosophy docs: `PRODUCT.md`, `SOUL.md`, `INTERFACE_CONTRACT.md`, `README.md`, `CHANGELOG.md`.

### Release / version metadata *[VERIFIED]*

- `pyproject.toml` (2026-06-17): backend Python project; `[tool.coverage.report] fail_under = 72`
- `frontend/package.json`: frontend version
- No formal release tags / `vX.Y.Z` found in the recent window; release metadata is informal (closeout.json files per phase)

---

## Part 2 — Product History: What ERLab Was Before the Recent Redevelopment

### Pre-wipe research outputs (HISTORICAL — deleted 2026-06-16) *[VERIFIED via `git show e2c0171~1:<path>`]*

The Phase 0 wipe (commit `e2c0171`, 2026-06-16) deleted a `sessions/260501-ivory-wolf/` tree with ~273 files, including **3 full research papers**:

| Deleted path | Title | Type | Provenance |
|---|---|---|---|
| `sessions/260501-ivory-wolf/data/GoT_NSR_Research_Paper.md` (+ `.tex`) | "Graph-of-Thought Meets Neuro-Symbolic Reasoning…" | Full paper | Pipeline-generated; 160–200 papers analyzed, 17 gaps, 6 proposals |
| `sessions/260501-ivory-wolf/data/ai_empirical_validity_paper.md` | "The Empirical Validity Crisis in AI…" | Full paper | **Hand-written by the Lead** — file notes "pipeline's synthesis stage was broken… produced only ~1,500-char stubs" |
| `sessions/260501-ivory-wolf/data/self_improvement_research_paper.md` | "From Self-Play to Self-Critique: A Survey of Self-Improvement Architectures…" | Survey/position paper | **Hand-written**, not pipeline output |

Plus ~5 named proposal collections deleted: **TopoReason**, **Neuro-SymbolicBench**, **CausalTrajectory**, **X-VoxelRoute**, **Guardian Angels** (under `got_proposals.md`, `nsr_proposals.md`, `got_nsr_unified_proposals.md`, `real_pipeline_proposal.md`).

> **Conclusion:** ERLab was NOT unproven before the recent redevelopment. There is repository evidence of prior operational use — both pipeline-generated and hand-authored full research papers existed and were used as the basis for substantive research output. They were removed in the Phase 0 wipe (a deliberate clean-baseline decision), not lost to failure.

### Currently-existing research outputs (VERIFIED) *[VERIFIED on disk]*

**10 full proposals** across 5 post-wipe runs (2026-06-16 → 2026-06-18), each with full section structure (Title / Abstract / Introduction / Related Work / Proposed Method / Expected Contributions / Evaluation Plan / Timeline / Risk Mitigation / References):

| Run | Domain | # proposals | Quality |
|---|---|---|---|
| `run_ca7ff01c7293` (2026-06-16) | (legacy hash run) | 2 | — |
| `run_4c29fd9f5a74` (2026-06-17) | — | 2 | — |
| `run_64432ab91250` (2026-06-17) | — | 2 | — |
| `run_4e60a37521f1` (2026-06-17) | — | 2 | — |
| `run_20260618_123654` (2026-06-18) | Edge AI and Privacy-Preserving ML | 2 | quality score 0.60 |

**8 stub proposals** (2026-07-15) across `run_20260715_000236/012549/012858/020419` — empty "Validated Text", `Ensemble Review` with all-empty fields and meta-review-failed score 0.5. These are **failed/broken pipeline runs**, not real outputs.

**Re-exports** in `data/exports/` mirror the 10 full proposals under sanitized filenames + 1 empty stub (`untitled-proposal.md`, 2026-07-15).

### Old user-facing capabilities *[VERIFIED]*

There was **never a dedicated `/papers` route**. Paper/proposal review has always been embedded inside `/ideas/:id` (the "proposal review workspace"), and that workspace **survived the redevelopment**. The EvidencePanel, provenance UX, remediation banner, fix-section button, and revision-history drawer components all exist at HEAD (`frontend/src/components/ideas/`).

Only 5 frontend files were ever deleted in git history (minor: `consciousness-state.tsx`, `useDarkMode.ts`, `useSSE.ts`, etc.). **No paper/bibliography/evidence UI was deleted.**

> The "recent frontend redevelopment" (F0/F1.x) was a **TypeScript-build + architecture refactor**, not a feature teardown. The original product-capability surface largely survived.

---

## Part 3 — Major Program History

Phases reconstructed from git log + closeout docs + `closeout.json` files. All phase outcomes marked VERIFIED are backed by machine-readable closeout artifacts or commit evidence.

| # | Phase | Objective | Outcome | Status | Improved |
|---|---|---|---|---|---|
| 1 | **Phase 0 wipe** (`e2c0171`, 2026-06-16) | Clean migration baseline from `elephant-rock-platform` | Clean baseline established; ~273 prior session files + 3 full papers removed | COMPLETE | GOVERNANCE / INTERNAL_INFRA |
| 2 | **P0.3** Vector access audit | Inventory + classify all ChromaDB accesses; migrate `research_papers` to governed run-scoped service | Every audited call site has terminal classification; scoped vector service built | COMPLETE | INTERNAL_INFRA / GOVERNANCE |
| 3 | **P0.4** Embedding access audit | Remove embedding from LLM chat providers; governed capability-bound lifecycle (5 sub-waves A0–A3, B0) | `LLMProvider.embed()` removed; capability ledger + V2 identity + atomic activation; controlled-provider E2E proof; 5-run seal 4418/25 passed/skipped | COMPLETE | INTERNAL_INFRA / GOVERNANCE |
| 4 | **P0.5** Configuration census | Prove every material `Settings` field has measurable production effect; eliminate silent fallbacks | 30/30 material fields with consumers + effect tests; 22 fallbacks removed; 5-run seal 4490/25 | COMPLETE | GOVERNANCE / INTERNAL_INFRA |
| 5 | **P1** Ranking surface audit | Audit ranking surfaces; build benchmark + contracts + policy framework | 3 surfaces audited; 12-case benchmark; contracts + policies built; **production activation NOT STARTED** | COMPLETE (infra); P1 OPEN | RESEARCH_QUALITY / INTERNAL_INFRA |
| 6 | **P1B** Baseline ranking experiment | Evaluate candidate policies against frozen gate (ΔnDCG@10 ≥ 0.03) | **GENUINE NEGATIVE RESULT**: best +0.0065, all candidates FAIL; 0 production changes | CLOSED (Gate 2) | RESEARCH_QUALITY |
| 7 | **P1C** Stronger embeddings (LM Studio) | Test stronger model passing the gate | **HOST AVAILABILITY FAILURE**: only 2/12 models stable; no practical candidate | CLOSED (Branch D) | RESEARCH_QUALITY |
| 8 | **P1D** TEI embedding experiment | Re-test ranking with HF TEI + `gte-large-en-v1.5` | **OUTCOME B**: reliable operation, NO significant ranking improvement; migration NOT authorized | CLOSED (Outcome B) | RESEARCH_QUALITY |
| 9 | **P1E.0** Benchmark discrimination audit | Diagnose saturation (S) vs architectural signal (A) vs both (M) | **OUTCOME M** (mixed/inconclusive): neither S- nor A-complete; recommended extension | CLOSED (diagnosis) | RESEARCH_QUALITY |
| 10 | **P1E.1** Benchmark extension | Build larger discriminative benchmark per M recommendation | 88 cases / 576 candidates / 444 grade records; all structural + grade targets pass; evaluation NOT done | CLOSED (corpus); eval NOT STARTED | RESEARCH_QUALITY / GOVERNANCE |
| 11 | **F0** Frontend TS recovery | Restore green TS build (101 → 0 errors) | 101→0; ratchet + 5-run seal; 690/690 vitest tests | COMPLETE / OPERATIONAL | INTERNAL_INFRA |
| 12 | **F1.x** Frontend architecture (F1.1–F1.7) | API contract layer, query lifecycle, mutation integrity, critical-flow, runtime errors, full migration | 7 waves; 58→0 unchecked API callers; 984 frontend tests ×5; 29 architecture seal tests | COMPLETE | PRODUCT (F1.5/F1.6) + INTERNAL_INFRA + GOVERNANCE |
| 13 | **P1D.2** Reviewer / diagnostic work | Construct product-grounded evaluation instrument (diagnostic + sealed cases) | 30-case diagnostic + blinded reviewer packages; protocol NOT sealed; awaits dual independent review | BLOCKED / DEFERRED | RESEARCH_QUALITY / GOVERNANCE |

### Cross-cutting observations *[INFERRED]*

- **P1 ranking blocker chain:** P1B (genuine negative) → P1C (host failure) → P1D (Outcome B) → P1E.0 (Outcome M) → P1E.1 (extension built, eval pending). The blocker diagnosis **migrated from "embedding model" (P1C/P1D) to "benchmark discriminative power" (P1E.0)** — a genuine refinement, not goalpost-moving.
- **Frontend track ran independently** of P1 research track from F0 (2026-07-21) through F1 closeout (2026-07-23); P1C explicitly recommended redirecting engineering effort to frontend.
- **Honest-negative-result discipline:** P1B, P1C, P1D all recorded integrity accounting (0 production changes / 0 threshold changes / 0 benchmark changes after freeze / 0 snapshot overwrites).
- **Repeated correction cycles concentrated in:** P1E.1 (4 protocol versions + custody breach disclosure), P1D.2 (schema revision + `diag_er_001` trap defect + coordinator identity separation), F1.5 (suppression + fake-success defects).

---

## Part 4 — Recent Work Timeline

**Repository period covered:** 2026-07-15 → 2026-07-25 (HEAD).
**Commits reviewed:** 228 in window (`git log --since=2026-07-15 --until=2026-07-25T04:00:00`).
**Detailed per-commit timeline:** see companion file `ERLAB_RECENT_WORK_TIMELINE.md`.

### Commit-chain `c1fa554` → `cea3ea1` (the requested window) *[VERIFIED]*

| Commit | Timestamp | Subject | Type | Effect |
|---|---|---|---|---|
| `c1fa5541a5efa9a57a2c6bc10ab3d0832ac29fa3` | 2026-07-24 06:40 | fix(p1e): correct top1-optimal empirical resolution | Correction | Bug fix in audit resolution |
| `d2e16ae6b82a3fdc13854ff8032874c1ce6bd20a` | 2026-07-24 23:26 | docs(p1e1): freeze benchmark extension protocol | Governance (protocol v1) | Docs only |
| `42ff0e661f2acfa15ccefbd94f2770dcaa3f353d` | 2026-07-24 23:57 | fix(p1e1): ground near-duplicate threshold in v2 references | Correction | Threshold recalibration |
| `00c6ffdc87e2e5057d205af6ee7de1db5e94cfad` | 2026-07-25 00:41 | feat(p1e1): construct and seal grade-free v3 candidate corpus + provenance | Planned work (artifact) | New benchmark content |
| `679bc0052d0851bef48ab87663166b7a08f85bd6` | 2026-07-25 01:03 | docs(p1e1): disclose calibration custody breach (protocol v3) | Governance patch (protocol v3) | Docs only |
| `36bbbc9d9275c342c0f7cb6cd486b9d9162aadf1` | 2026-07-25 01:09 | fix(p1e1): canonicalize candidate artifact protocol identity + disclose breach | Correction + governance | Artifact identity rebinding |
| `2a32254a66bacec492493d9655b61a81525fb3ad` | 2026-07-25 01:26 | feat(p1e1): cal/dev adjudication, blind held-out, extension identity | Planned work | New adjudication content |
| `3e6d09e73972d24a070e7e98079126be5fb06d73` | 2026-07-25 01:35 | docs(p1e1): seal adjudication provenance and custody status | Governance | Docs only |
| `af2f131f2851ae1064750e54b29278d2ce8d3028` | 2026-07-25 02:07 | docs(p1e1): authorize preserved-v2 judgment inheritance (protocol v4) | Governance patch (protocol v4) | Docs only |
| `a6c35e670f67a0331cc71074caf229e52b02b9c2` | 2026-07-25 02:13 | docs(p1e1): close inheritance deviation and complete custody transfer | Governance | Docs only (custody relocation) |
| `cea3ea16378ef7bbf7848cc31febf93af2478841` | 2026-07-25 03:09 | docs(p1e1): close benchmark extension diagnosis | Governance | Docs only (HEAD) |

**No commits exist after `cea3ea1`** — HEAD is the tip.

### Repeated correction cycles identified *[VERIFIED]*

| Cycle | Commits | Nature |
|---|---|---|
| **Protocol v1 → v4** | `d2e16ae` (v1 freeze) → `42ff0e6` (v2 threshold grounding) → `679bc00` (v3 custody-breach disclosure) → `af2f131` (v4 inheritance authorization) | 4 protocol versions in ~2.5 hours |
| **Near-duplicate threshold recalibration** | `42ff0e6` ("ground near-duplicate threshold in v2 references") | Threshold re-derived from v2 references |
| **Allocation / split correction** | `2f9031d` (P1E.0, "correct split-manifest case→split mapping") — pre-window | Earlier correction carried forward |
| **Held-out calibration-access disclosure** | `679bc00` (v3) disclosed historical held-out access (2 cases, 4 texts, 0 judgments) | Custody breach acknowledged |
| **Artifact identity rebinding** | `36bbbc9` ("canonicalize candidate artifact protocol identity") | Candidate corpus re-fingerprinted |
| **Inherited-judgment authorization** | `af2f131` (v4) authorized 180 byte-identical v2 cal/dev records to inherit | Bounded inheritance |
| **Custody relocation** | `a6c35e6` ("complete custody transfer") — reconciliation map moved outside repo to `C:\Next-Era-Erlab-Custody\` | Custody transfer |
| **Commit 2 / Commit 3 governance patches** | `679bc00` (Commit 2 = v3 disclosure) and `2a32254`/`3e6d09e` (Commit 3 = cal/dev + held-out + provenance seal) | Two of the formal numbered commits in the closeout chain |

> The timeline reports what happened. It does not criticize or defend. See Part 11 for the drift analysis.

---

## Part 5 — P1E.0 and P1E.1 Final State

All values below are **VERIFIED** against the sealed artifacts in `data/evaluation/` and `docs/research/`. Every value was cross-checked against the actual JSON artifacts in this session.

### P1E.0 — Benchmark Discrimination Audit

| Field | Value | Source |
|---|---|---|
| Objective | Diagnose whether P1B/P1D failure is benchmark saturation (S), architectural signal (A), both (M), or neither | `docs/research/p1e_benchmark_discrimination_audit_protocol.md` |
| Benchmark size | **44 audited (cal+dev)** out of 66 total v2 cases (22 cal + 22 dev + 22 held-out) | `data/evaluation/p1e_frozen_split_manifest.json` |
| Policies compared | 5-run matrix: `legacy_lexical`, `p1b_semantic`, `tei_semantic`, `p1b_hybrid_rrf`, `tei_hybrid_rrf` | protocol §5 |
| **Outcome** | **M** (mixed / inconclusive) | `p1e_discrimination_audit.json` `section7_diagnosis.outcome: "M"` |
| Saturation findings | R1 pass (29/44 zero headroom); R2 pass (top1_optimal=1.0); R3 pass (<2 hard negs in 100%); R5 pass (power-limited); **R4 FAILS** (lexical-vs-semantic underpowered, not no_detected_difference) | diagnosis JSON |
| Power findings | No pairwise comparison significant (every 95% CI includes 0; every permutation p ≥ 0.05); MDEs 0.01376–0.03271 | `data/evaluation/p1e_policy_pairwise_comparison.json` |
| Error classes | 2 classified recurring: `lexical_aliasing` (4 cases), `near_duplicate_candidates` (4 cases); plus 2 hypothesis + 3 not_inferable | diagnosis JSON |
| Final accepted commit chain | `2032579` → `2f9031d` → `25d56df` → `d3420d6` → `c1fa554` → `063d060` | `p1e_benchmark_discrimination_audit_protocol.md` |
| Why Outcome M | Neither S nor A complete. S incomplete (R4 fails: lexical-vs-semantic underpowered). A incomplete (A1 18% headroom > 0.05 vs 40% required; A2 only 5 grade-0 hard negs; A4 no adequate-power+detected-effect). Precedence: neither complete → M | diagnosis JSON |

### P1E.1 — Benchmark Extension

| Field | Value | Verification |
|---|---|---|
| Final effective protocol lineage | v1 → v2 → v3 → **v4 (effective)** | `p1e1_adjudication_provenance.json` `effective_protocol_v4_commit`; `af2f131` |
| Case composition | **88 total** (33 cal + 33 dev + 22 held-out); 44 v2_lineage + 44 fully_new | `p1e1_split_manifest.json` `total_cases: 88` |
| Candidate count | **576** | `p1e1_candidate_package.json` direct count = 576 |
| Cal/dev vs held-out split | 66 cal+dev : 22 held-out (3:1); cal 33 / dev 33 (even) | split manifest |
| Inherited vs fresh judgments | **180 inherited** v2 cal/dev (byte-identical) + **264 fresh** (132 injected + 132 fully-new); total 444 | `p1e1_caldev_adjudication.json` |
| Structural target results | All pass: candidate_count 6–8/domain balanced; id_collisions_zero; lexical_trap 48/12 target; near_dup 46/12 target (threshold 0.861630662); preserved_content_unchanged | `p1e1_construction_provenance.json` |
| Grade-dependent target results | All pass (`all_grade_targets_pass: true`). Grade dist {0:147, 1:67, 2:118, 3:112}. 65/66 cases ≥2 hard negs; 36/66 unique-best; 36 misleading near-dup; 66 lexical-confuser | extension JSON |
| **Projected MDE** | **0.02938** (SD=0.08518, n=66) | `conservative_projected_mde: 0.02938` — **design projection, NOT measured** (`measured_in_p1e1: false`) |
| Calibration-access history | Historical custody breach (v3): 2 held-out cases (`ml_disc_nd_001`, `nlp_ret_nd_001`), 2 held-out reference pairs, 4 held-out candidate texts, **0 judgments** accessed. Final admissible calibration: 4 cal/dev pairs, 0 held-out | protocol v3 |
| Custody status | `transfer_status: accepted` (2026-07-24T23:09:05Z). Construction copy deleted; reconciliation map (154 entries) stored OUTSIDE repo at `C:\Next-Era-Erlab-Custody\p1e1_reconciliation_map.json`. Operationally blinded. **Independent-custody limitation flagged as P1E.2 prerequisite, not P1E.1 failure** | `p1e1_reconciliation_map_custody_receipt.json` |
| Final fingerprint status | `final_adjudicated_v3_fingerprint: "pending_p1e2"`. Candidate corpus fingerprint itself sealed (`4da4e53d…`) | extension JSON, adjudication provenance |
| Policy-evaluation status | `policy_evaluation_status: "not_started"`; `production_retrieval_decision: "not_made"`; `p1e3_policy_evaluation: "not_performed"` | extension JSON |
| Final commit chain (P1E.1) | `d2e16ae` → `42ff0e6` → `00c6ffd` → `679bc00` → `36bbbc9` → `2a32254` → `3e6d09e` → `af2f131` → `a6c35e6` → `cea3ea1` | git log |

### Cross-check of all 14 claimed values

**ALL 14 VERIFIED. Zero DISAGREES. Zero NOT_FOUND.**

| Claim | Verdict |
|---|---|
| 88 total cases | **VERIFIED** |
| 33 calibration | **VERIFIED** |
| 33 development | **VERIFIED** |
| 22 held-out | **VERIFIED** |
| 576 candidates | **VERIFIED** |
| 444 cal/dev grade records | **VERIFIED** |
| 180 inherited judgments | **VERIFIED** |
| 264 fresh judgments | **VERIFIED** |
| 147 grade-0 records | **VERIFIED** |
| 65/66 cases with ≥2 primary hard negatives | **VERIFIED** |
| 36 misleading near-duplicate cases | **VERIFIED** |
| 66 lexical-confuser cases | **VERIFIED** |
| conservative projected MDE 0.02938 | **VERIFIED** (design projection, not measured) |
| final adjudicated v3 fingerprint pending P1E.2 | **VERIFIED** |

### Three-way distinction (per contract)

| Quantity | Status |
|---|---|
| **Measured P1E.0 results** | VERIFIED — 5-run audit on 44 cases; no significant pairwise difference; Outcome M |
| **Projected P1E.1 sensitivity** | VERIFIED as a *projection* — MDE 0.02938 is a design value; `measured_in_p1e1: false`; forbidden terms include "achieved MDE" / "measured P1E.1 MDE" |
| **Future P1E.3 measured policy results** | UNKNOWN / NOT PERFORMED — `p1e3_policy_evaluation: "not_performed"` |

---

## Part 6 — Current Capability Matrix

**Capability counts:** 27 capabilities assessed. Companion file `ERLAB_CAPABILITY_MATRIX.md` contains the full matrix; summary counts below.

| Status | Count |
|---|---|
| WORKING | 10 |
| PARTIAL | 4 |
| PRESENT_BUT_UNVERIFIED | 0 |
| NOT_EXPOSED | 7 |
| MISSING | 6 |
| UNKNOWN | 0 |

**Backend exists but NO UI (NOT_EXPOSED):** seed-paper input, literature ranking, evidence extraction, claims viewer, full paper generation, literature quality eval, external validation.

**MISSING (no backend, no UI):** research-project concept, source review, evidence tables, evidence packets, arguments, argument-coherence evaluation.

**Key wiring gaps (UI components exist but are NOT rendered by any page):** `evidence-panel.tsx`, `proposal-review-panel.tsx`, `remediation-banner.tsx`, `quality-check-panel.tsx`, `radar-chart.tsx`, `evaluation-card.tsx`. The live `idea-detail.tsx` renders lightweight inline versions instead.

---

## Part 7 — Interface and Product State

### Current frontend routes (20) *[VERIFIED]*

See Part 1. Notably absent: `/papers`, `/evidence`, `/claims`, `/arguments`, `/sources/:id`, `/evaluations`, `/proposals` (the proposal workspace is `/ideas/:id`).

### What the interface can currently do *[VERIFIED]*

A user can, entirely through the UI:
1. Launch a research run (`/pipeline/new` → `POST /pipeline/run`) with domain + strategy + (advanced) keyword `search_queries`.
2. Watch run progress (`/runs/:id`, SSE + polling, stage timeline, tree search, ideas list).
3. Browse ideas (`/ideas`) and gaps (`/gaps`).
4. Read a generated proposal at `/ideas/:id` — proposal body, novelty axes (`ScoreReport`, `NoveltyReportView`), feasibility report, mechanical metrics, quality checks per section.
5. Refine: `POST /ideas/:id/refine`, per-section fix (`FixSectionButton`), feedback form, revision history drawer.
6. Govern: queue approve/deny (`/governance`); per-idea governance panel (approve / needs_changes / deny + audit timeline).
7. Export: PDF + Markdown from idea dialog; Markdown + LaTeX + BibTeX from run-detail.
8. Resume failed runs (`/runs/:id` Resume button → `POST /pipeline/resume/{id}`).
9. Search and ingest literature (`/literature`).
10. Browse knowledge graph, memory, sessions, costs, traces, ops, plugins, settings.

### Backend capabilities NOT exposed in UI *[VERIFIED]*

- Full paper generation (pipeline has `PaperSynthesizer` + `PaperSynthesisStage`; UI only surfaces proposals).
- Claims library (`backend/pipeline/claims/` exists, is orphaned, has no API route, no UI).
- Arguments (no backend, no UI).
- Evidence tables / packets (no backend, no UI).
- Argument-coherence / literature-quality evaluation (no endpoints wired).
- External validation (no `/validation` route; backend `verification/` is internal-only).
- Dedicated ranking-visibility screen.
- Dedicated source/paper-review screen (per-paper deep review).

### Old capabilities that may have regressed *[INFERRED]*

The proposal-review workspace at `/ideas/:id` survived, but several richer components are **dead code** (not imported by any page): `evidence-panel.tsx` (full per-reference resolution), `proposal-review-panel.tsx` (ensemble review with per-perspective methodology/novelty/clarity scores), `remediation-banner.tsx` (citation-audit consumption). The live page renders lighter inline versions. This is INFERRED regression of *depth*, not loss of the underlying capability.

### What still requires CLI / direct artifact access *[VERIFIED]*

- Running `erock generate` with a natural-language research question (UI only accepts `domain` + keyword `search_queries`; no NL question field).
- Generating a full paper (CLI strategy `deep_research`/`academic_proposal` produces it; UI does not expose paper vs proposal toggle).
- BibTeX export of a single idea (only run-level BibTeX exists in UI).
- All benchmark / P1E.* operations (`scripts/p1e1_*.py`).

### Can a user complete a research paper entirely through the interface?

**NO — partially achievable.** A user can produce an *evaluated, exported proposal* end-to-end via UI. They **cannot** produce a full research *paper* via UI (only proposals), and there is **no natural-language research-question input** (only domain + keywords). See `ERLAB_CAPABILITY_MATRIX.md` for the exact end-to-end journey gaps.

### Visual consistency, migrations, debt *[REPORTED]*

- `PRODUCT.md` defines the design contract (reading is the center; trust must be earned visibly; machine proposes, human decides).
- `INTERFACE_CONTRACT.md` (24KB) codifies the interface rules.
- F0/F1.x completed the TS-build + architecture migration (no visual redesign in this window).
- 72 pre-existing ESLint warnings left as frozen debt (F0 closeout).
- `frontend/api-unchecked-budget.json`, `ts-budget.json`, `lint-budget.json` are frozen ratchets at 0.

---

## Part 8 — Test and Quality State *[VERIFIED — counted/run this session]*

### Counts

| Suite | Files | Functions / cases |
|---|---|---|
| Python (`backend/tests/`) | 463 | 1180 test functions (4822 collected node IDs) |
| Frontend (`frontend/src/`) | 122 | ~1031 `it(`/`test(` calls |

### Current green/failing state

| Run | Result | Source |
|---|---|---|
| **Architecture seal suite** (`backend/tests/architecture/`) | **1 FAILED, 40 passed** | Run this session |
| **P1E.0 + P1E.1 ranking tests** (5 files) | **116 passed, 3 skipped** (skips = closeout-mode gated) | Run this session |
| **DB migration tests** (`test_initial_migration.py`) | 3 passed | Run this session |
| **`.pytest_cache/v/cache/lastfailed`** (2026-07-25 03:08) | lists 88 failing node IDs — **STALE**: spot-checked DB migration tests now pass | cache file |

**VERIFIED current regression:** `backend/tests/architecture/test_p0_5_seal.py::test_no_direct_os_environ_in_production` FAILS because `backend/ranking/generate_embedding_snapshot.py:62` reads `os.environ.get("P1C_SNAPSHOT_TAG", ...)` directly, violating the P0.5 config-effectiveness seal. **This is a real, current architecture-seal regression introduced during the P1B/P1C snapshot work and not yet repaired.**

> The 88-entry `lastfailed` cache overstates current failures — it appears to be from an earlier run with a different DB/code state. DB migration tests that it lists as failing now pass. Treat the 88 number as **REPORTED and stale**, not as current VERIFIED failure count. The architecture-seal failure IS current and VERIFIED.

### Test-type classification *[VERIFIED]*

| Type | Locations | Notes |
|---|---|---|
| Unit (mocked) | most of `test_pipeline/`, `test_api/`, `test_ranking/`, `test_knowledge/`, etc. | Root conftest provides `FakeLLMProvider`, mocks `chromadb`/`google.generativeai` |
| Integration | `integration/test_pipeline_smoke.py`, `test_integration/` (2 files) | `@pytest.mark.integration`; uses `DummyEmbeddingProvider` |
| Benchmark | `test_benchmarks/` (6) + selected `test_pipeline/` + `test_ranking/test_benchmark_integrity.py` | `pytest-benchmark` |
| Architecture / invariant | `architecture/` (5 files, 41 tests) | AST-based forbidden-symbol/contract seals |
| E2E / product flow | NOT in pytest | Standalone scripts: `run_e2e_pipeline.py`, `e2e_quarantine_integration.py` |
| Human validation | P1D.2 reviewer packages (`docs/retrieval/p1d2_reviewer_package_*.jsonl`) | NOT yet executed — protocol unsealed, awaits dual independent review |

### Skipped tests *[VERIFIED]*

- 30 Python skip directives total: 6 `@pytest.mark.skipif`, 1 `@pytest.mark.skip`, 23 runtime `pytest.skip()`.
- All environment-gated (Docker, ChromaDB, LM Studio, opentelemetry, ports, closeout mode).
- 0 frontend skips. 0 `xfail`.
- CI selector: `pytest -p no:asyncio -m "not slow and not integration"`.

### REPORTED green claims (historical, not current)

- P0.4 B0 closeout: "4188 passed, 50 skipped" at entry commit (closeout.json).
- P0.5 closeout: "4490 passed/25 skipped ×5 runs".
- P1B closeout: "121 ranking tests pass".
- F1.7 closeout: "984 frontend tests ×5, 320 backend + 4 skipped".

These predate today's run and the architecture-seal regression. **Do not cite as current green status.**

---

## Part 9 — Artifact and Governance Inventory

Companion JSON: `docs/project/erlab_current_state_inventory.json` (relocated from the requested `data/project/` path because `.gitignore` rule `data/` is documented "NEVER commit"; the inventory is a hand-authored reporting artifact and lives alongside its companion markdown reports). Selected highlights:

### Research outputs *[VERIFIED]*

- 10 full proposals in `data/runs/run_*/proposals/` (2026-06-16 → 2026-06-18).
- 8 stub proposals (failed runs, 2026-07-15) — not real outputs.
- 3 historical full papers deleted in Phase 0 wipe (recoverable via `git show e2c0171~1:<path>`).

### Benchmark artifacts *[VERIFIED]*

`data/evaluation/` — 16 JSON files for P1E.0/P1E.1 (split manifest, candidate package, caldev adjudication, blind held-out package, construction/adjudication/mining provenance, custody receipt, diagnosis, case diagnostics, pairwise comparison).

`docs/p1b_snapshot/` — 10.8MB frozen ranking snapshot; `docs/p1b_gate1/`, `docs/p1b_gate2/` — blind-adjudication packages.

### Evaluation reports *[VERIFIED]*

`docs/research/p1e_benchmark_discrimination_audit.{md,json}`, `docs/research/p1e1_benchmark_extension.md` + 4 protocol versions; `docs/retrieval/p1d_closeout.md`, `p1d_retrieval_need_spec.{md,json}`, `p1d_failure_distribution.json`; `reports/retrieval/p1d_failure_analysis.md`, `p1d2_diagnostic_seed_review.md`.

### Protocols / closeouts *[VERIFIED]*

Per-phase `*_closeout.{md,json}` for P0.3 (closeout md only), P0.4 (a0–a2, b0, main), P0.5, P1, P1B, P1C; `docs/frontend/f1_*.md` + `f1_closeout.{md,json}`; P1D closeout in `docs/retrieval/`; P1E.0/P1E.1 closeouts in `docs/research/`.

### Audit seals *[VERIFIED]*

5 architecture-seal tests in `backend/tests/architecture/` (P0.4 A1/A2/A3/B0, P0.5) — AST-based forbidden-symbol scanners. **1 currently fails** (P0.5 — see Part 8).

### Frontend validation reports *[VERIFIED]*

`docs/f0_frontend_recovery/F0_BASELINE.md`, `F0_CLOSEOUT.md`, `baseline_tsc_errors.txt`, `remaining_after_cat1_7.txt`; `docs/frontend/f1_runtime_contract_audit.{md,json}`, `f1_7_architecture_inventory.{md,json}`; `docs/frontend-ts-baseline.md`.

### Duplicate / superseded / parallel artifacts

- **4 P1E.1 protocol versions** (`...protocol.md` v1, `_v2`, `_v3`, `_v4`) — v4 is effective; v1–v3 are historical.
- **Stale `benchmarks/latest.json`** (2026-05-13) references 65 deleted pre-wipe runs — superseded by the P1B/P1E benchmark lineage.
- **Multiple snapshot dirs**: `docs/p1b_snapshot/` (frozen control) vs `docs/p1c_snapshots/<tag>/` (P1C candidates) — parallel by design (P1C isolation).
- **`p1e1_benchmark_extension.json` vs `p1e1_benchmark_extension_diagnosis.json`** — extension record vs diagnosis mirror; consistent values.
- **Two export route files**: `backend/api/routes/export.py` (legacy `/api/export/...`) and `exports.py` (`/api/v1/export/...`) — parallel, both mounted.

---

## Part 10 — Open, Blocked, and Deferred Work

Consolidated table. See companion `ERLAB_OPEN_DECISIONS.md` for full detail.

| Item | Status | Blocker | Blocks product? | Smallest next action |
|---|---|---|---|---|
| **P1 ranking quality objective** | OPEN | No candidate policy has passed the frozen gate; blocker refined to "benchmark discriminative power" | Indirect (research quality) | Decide retrieval architecture (P1E.3 or new approach) |
| **P1E.2** held-out adjudication | BLOCKED | Custody prerequisites: independent-custody requirement; reconciliation map currently outside repo | NO (research R&D) | Establish independent custody; adjudicate held-out |
| **P1E.3** frozen policy comparison | BLOCKED | Depends on P1E.2 (held-out must be adjudicated first) | NO (research R&D) | Unblock P1E.2 |
| **P2** | BLOCKED | P1 unresolved | NO (research R&D) | Resolve P1 |
| **Interface completion** | OPEN | No NL research-question input; no full-paper UI; dead-code rich components; 1 architecture-seal regression | YES (product surface) | Add research-question field; repair P0.5 seal |
| **End-to-end paper workflow** | OPEN | Full paper generation not exposed in UI | YES (product) | Expose paper vs proposal toggle |
| **Comparison with old papers** | DEFERRED | Old papers deleted in Phase 0 (recoverable via git) | NO | Recover via `git show e2c0171~1:<path>` if comparison is needed |
| **Retrieval architecture decision** | OPEN | P1E.0 outcome M inconclusive; P1E.1 evaluation not run | Indirect | Run P1E.3 once P1E.2 unblocked |
| **Held-out adjudication** | BLOCKED | P1E.2 custody prerequisites | NO | Independent custody |
| **Product release readiness** | OPEN | E2E paper workflow incomplete; architecture-seal regression; benchmark lineage unresolved | YES | Close interface gaps; repair seal |
| **P1D.2 dual independent review** | BLOCKED | 81 provisional single-pass judgments by one author; protocol unsealed | NO (research R&D) | Recruit independent reviewers |
| **P0.5 architecture-seal regression** | OPEN | `generate_embedding_snapshot.py:62` direct `os.environ` read | NO (governance) | Route `P1C_SNAPSHOT_TAG` through `Settings` |
| **Stale `benchmarks/latest.json`** | OPEN | References 65 deleted pre-wipe runs | NO (governance) | Delete or supersede |

---

## Part 11 — Drift and Rework Analysis

**Window measured:** 2026-07-15 → 2026-07-25 (228 commits). *[VERIFIED via `git log` + per-commit file inspection]*

### Commit allocation

| Category | Count | % of 228 |
|---|---|---|
| Commits WITH production code (non-test `.py`/`.ts`/`.tsx`, excluding `scripts/`) | **121** | 53% |
| Commits with ONLY test / script code | **54** | 24% |
| Commits with NO code (docs/data/json/yaml/config/md only) | **53** | 23% |

### Commit-type breakdown (by conventional-commit prefix) *[VERIFIED]*

| Prefix | Count |
|---|---|
| `feat` | 75 |
| `docs` | 63 |
| `test` | 34 |
| `fix` | 29 |
| `refactor` | 17 |
| `data` | 6 |
| `eval` | 3 |
| `chore` | 1 |

### Phase-correction rework *[VERIFIED]*

- **P1E.1 protocol iterated 4 versions** in ~2.5 hours (v1 → v2 threshold grounding → v3 custody-breach disclosure → v4 inheritance authorization).
- **P1D** had metric-drift correction (66 vs 44 cases) requiring exact-parity re-proof.
- **P1D.2** underwent schema revision + the `diag_er_001` false-support trap defect (weakened-then-restored) + coordinator identity-map separation.
- **F1.5** had a suppression + fake-success defect cycle (`_do_ingest` `except ImportError` returning fake success; QueryClient `eslint-disable` suppressions).

### Drift conclusions *[INFERRED]*

- **Durable product value created:** F0 (green TS build + ratchet), F1.1–F1.7 (API contract layer, query/mutation integrity, runtime observability, ingest persistence truthfulness). These are durable frontend-infrastructure improvements.
- **Durable research-quality value created:** P1B (honest negative result with integrity accounting), P1D (Outcome B + parity proven), P1E.0 (Outcome M diagnosis), P1E.1 (larger discriminative benchmark corpus). The diagnosis genuinely refined from "embedding model" to "benchmark discriminative power."
- **Corrective rework:** 29 `fix` commits (13%); P1E.1's 4 protocol versions; P1D parity re-proof; P1D.2 trap defect; F1.5 suppression/defect cycle.
- **Governance overhead:** 63 `docs` commits (28%) + 6 `data` commits; P1E.1 alone has ~6 governance-patch commits in its final 11-commit chain.
- **Should not be repeated:**
  - Custody breaches requiring protocol disclosures (P1E.1 v3) — access discipline upstream of corpus construction would avoid the rework.
  - Split-discipline drift requiring parity re-proof (P1D) — frozen-split manifests up front.
  - Direct `os.environ` reads in production code violating seals (current P0.5 regression) — route through `Settings` at feature-add time.
  - Dead-code UI components (`evidence-panel.tsx`, etc.) — wire-or-remove at completion of each wave.

> No blame assigned. Focus is on project mechanics. INFERRED where not directly measurable.

---

## Part 12 — Verified Current State

### What ERLab currently is *[VERIFIED]*

Elephant Rock Research Lab is an AI-augmented research-proposal generation platform: a FastAPI + SQLAlchemy + Alembic backend with a 16-stage research pipeline (literature search → ingestion → gap analysis → idea generation → novelty → feasibility → proposal synthesis → adversarial review → evaluation → paper synthesis → citation audit → export), and a React + TypeScript SPA frontend with 20 routes. It also contains a substantial retrieval-ranking benchmark and governance infrastructure (capability ledger, vector scope, config-effectiveness seals).

### What it can currently do *[VERIFIED]*

- Generate evaluated research **proposals** end-to-end via UI (domain + keywords → proposal + novelty/feasibility scores + citations + export).
- Search and ingest literature; browse ideas, gaps, knowledge graph, memory, sessions, costs, traces.
- Govern (approve/deny), refine (per-section fix, feedback, revision history), resume failed runs.
- Export Markdown / LaTeX / BibTeX (run-level) and PDF / Markdown (idea-level).
- Run a sealed 88-case retrieval benchmark with 576 candidates and 444 grade records.

### What has been proven *[VERIFIED]*

- P1B: no candidate ranking policy passes the frozen gate (genuine negative, integrity accounting clean).
- P1C: no practical stronger-embedding candidate on this host.
- P1D (Outcome B): TEI is operationally reliable but produces no significant ranking improvement.
- P1E.0 (Outcome M): benchmark is neither saturated nor architecturally complete; the blocker is discriminative power.
- P1E.1: a larger discriminative benchmark (88 cases, all structural + grade targets pass) is constructed and sealed at the corpus + cal/dev layer; projected MDE 0.02938 is a design projection, not a measurement.

### What has only been REPORTED (not independently re-proven) *[REPORTED]*

- Historical green test counts (4188 / 4490 / 121 / 984) — predate today's run.
- P0.4 controlled-provider E2E proof (live provider certification NOT executed; controlled-provider proof only).
- P1D.2 81 provisional single-pass judgments (single-author, `eligible_for_scoring: false`).

### What remains UNKNOWN

- Actual P1E.1 paired-policy MDE (P1E.3 not performed).
- Whether any retrieval policy will pass the extended benchmark.
- Current full backend test-suite green count (lastfailed cache is stale; only architecture + ranking suites spot-checked this session).

### What is closed (do not reopen)

- Phase 0 wipe, P0.3, P0.4, P0.5, P1 (infra), P1B, P1C, P1D, P1E.0, P1E.1 (corpus + cal/dev), F0, F1.1–F1.7.

### What remains blocked

- P1E.2 (custody prerequisites), P1E.3 (depends on P1E.2), P2 (depends on P1), P1D.2 dual independent review.

### What should NOT be reopened

- Frozen P1B snapshot, frozen P1E.0 corpus + evaluator, sealed P1E.1 candidate corpus + cal/dev adjudication. Re-evaluation requires new versioned experiments per the integrity accounting of each closeout.

### Evidence still needed before the next roadmap *[INFERRED]*

1. **Current full-suite test state** — a fresh pytest run to displace the stale `lastfailed` cache and establish a current green/failing baseline.
2. **Repair of the P0.5 architecture-seal regression** (`generate_embedding_snapshot.py:62`) — confirms whether the config-effectiveness contract still holds.
3. **P1E.2 custody independence** — whether independent custody can be established (current custodian resides within governed environment; flagged as a prerequisite, not a failure).
4. **P1E.3 measured policy MDE** — the actual sensitivity of the extended benchmark, replacing the 0.02938 projection.
5. **End-to-end product flow validation** — whether the UI can produce an *evaluated full paper* (not just proposal), since paper generation exists in the pipeline but is not UI-exposed.
6. **Decision on dead-code UI components** — wire or remove `evidence-panel.tsx`, `proposal-review-panel.tsx`, `remediation-banner.tsx`, etc.

---

*End of report. This document is a reporting artifact only. No product, benchmark, protocol, or research artifact was modified in its production.*
