# Phase 0 Closeout — Establish the Executable Product Baseline

> **Phase 0 closeout.** Contains only the fields specified in Work Package 0E.
> **No product feature added. No P1E artifact changed.**

> **Accepted corrections (record-accuracy follow-up).** On acceptance, two refinements superseded the original Phase 0 wording and were folded back into this record and into `ERLAB_TEST_BASELINE.md` / `ERLAB_HISTORICAL_OUTPUT_BASELINE.md`:
> 1. **The 136 failures remain real test failures.** Independent-file passing is evidence *for* the test-isolation-defect hypothesis, not proof that all 136 are non-defects. A full CI-selector run that fails is itself an engineering defect. Classification: `Backend runtime defect = not established; Test-suite isolation defect = strongly indicated; Full-suite health = failing; Blocks Phase 1 = no; Must remain tracked = yes`.
> 2. **The recovered paper is a workflow fixture, not a quality gold standard.** No evaluation artifact or machine-readable run provenance survived, and its 10 references have not been independently validated. Citation/scientific-quality validation belongs in the later product-comparison phase.
>
> These are documentation-only corrections; no Phase 0 work was reopened, no seal changed, no artifact re-recovered.

| Field | Value |
|---|---|
| **Baseline commit** | `d5990bc4e603767dc1282a7044122ed5e9be8ea5` |
| **Final commit** | the tip of `feat/quarantine-and-frontend-redesign` after this closeout (Commit 3 in the table below; this file deliberately does not record its own hash, since doing so is self-referentially unstable) |
| **Working tree at closeout** | clean |

---

## Repository-lineage result *[VERIFIED — see `ERLAB_REPOSITORY_LINEAGE.md`]*

- `origin` (`C:\Next-Era\elephant-rock-platform`, 529 commits) is the pre-Phase-0 repo and a **strict ancestor** of `feat`. Both local `master` and `origin/master` contribute **0 commits** not on `feat`.
- The `erlab/` package **does not exist as code** in either repo (documentation label only).
- Of the nine queried capabilities (`evidence_table`/`evidence_packet`, `argument_coherence`, `multi_paper_synthesis`, `external_validation`, `bibliography`, `paper_draft`, `release_manifest`, `audit_seal`): **none were ever deleted modules.** Three exist under different names (`bibliography`→`bibtex_export`, `paper_draft`→`paper_synthesizer`, `audit_seal`→architecture-seal tests); the other six were never implemented in either repo (pickaxe empty across 1,367 commits).
- The only deleted source file (`backend/pipeline/orchestrator.py`, 120 KB monolith) was a **refactor into the `backend/pipeline/orchestrator/` package** — logic preserved, not lost.
- **No accidental rebuild risk.** Nothing to selectively recover.

## Recovered historical output *[VERIFIED — see `ERLAB_HISTORICAL_OUTPUT_BASELINE.md`]*

- `docs/project/phase0/historical_baseline/GoT_NSR_Research_Paper.{md,tex}` — recovered **byte-identical** from `e2c0171^` (original blob hashes `c59b75a`/`e59f1b3` match `git hash-object` of recovered files).
- Authentic pipeline-generated full paper: 4,347 words, 8 sections, 10 numbered references, documented pipeline config in Appendix A.
- **Role: historical workflow fixture** (compare completion / length / structure / section coverage / export formats / user effort). **Not a quality gold standard** — no evaluation artifact survived, no machine-readable run provenance survived, and its 10 references have not been independently validated. Citation and scientific-quality validation belongs in the later product-comparison phase.
- The two hand-written deleted papers are NOT presented as pipeline proof.

## Architecture-seal result *[VERIFIED — see `ERLAB_TEST_BASELINE.md` §Step 1]*

- **P0.5 seal green: 41/41 architecture tests pass** (was 40/41).
- Repair: `generate_embedding_snapshot.py` now reads `p1c_snapshot_tag` via `Settings` (`EROCK_P1C_SNAPSHOT_TAG`) instead of `os.environ`. Focused config-effect test updated and passing.

## Backend test baseline *[VERIFIED — fresh execution, no `.pytest_cache`]*

| Suite | Result |
|---|---|
| Architecture seals | **41 passed** |
| Ranking suite | **253 passed, 3 skipped** (closeout-mode gated) |
| Full CI selector (`-p no:asyncio -m "not slow and not integration"`) | **4580 passed, 136 failed, 47 skipped, 29 deselected** (241 s) |

**136 full-suite failures — classification:** test-isolation defect strongly indicated (three sampled failing files `test_gateway.py`, `test_governance_decisions.py`, `test_crossref_source.py` all pass 100% in isolation), but **runtime-defect question not established** and **full-suite health is failing**. Stable classification: `Backend runtime defect = not established; Test-suite isolation defect = strongly indicated; Full-suite health = failing; Blocks Phase 1 = no; Must remain tracked = yes`. **Zero failures caused by the seal repair** (no failing test matches `snapshot|p1c|p0_5|config|architecture`). Recorded as tracked debt; not expanded into a repair program in Phase 0.

## Frontend test baseline *[VERIFIED — fresh execution]*

| Check | Result |
|---|---|
| Typecheck (`tsc -b`) | **PASS** — clean |
| Tests (`vitest run`) | **122 files, 984 passed, 0 failed** (59.7 s) |
| Production build (`vite build`) | **PASS** — 8.62 s |
| Lint (`eslint .`) | **0 errors, 63 warnings** |
| TS / API / lint budget ratchets | **all hold** (0/0/59; lint down from baseline) |

## Stale benchmark pointer disposition *[VERIFIED — see `ERLAB_ARTIFACT_AUTHORITY.md`]*

- **`benchmarks/latest.json` does not exist** — not on disk, not in HEAD, not in any branch, not in the pre-Phase-0 platform repo, and consumed by no code. The current-state report's "stale pointer" entry was a phantom and is corrected here.
- **No action taken** (nothing to supersede/remove). Authoritative retrieval lineage recorded: P1B snapshot → P1E.0 audit → P1E.1 sealed extension → (P1E.2/P1E.3 not yet completed).

## Remaining verified failures / tracked debt

1. **136 backend full-suite failures — full-suite health failing.** Test-isolation defect strongly indicated (3 sampled files pass in isolation); runtime-defect question **not** established (the other 133 were not individually isolated, so some could be genuine defects masked by the pollution). **Must remain tracked** until a clean full-suite run is achieved. Not blocking Phase 1; candidate for early Phase 4 investigation.
2. **3 ranking skips** (intentional closeout-mode gating of P1E.0/P1E.1 tests). Not failures.
3. **63 frontend lint warnings** (within frozen budget of 72; not errors). Pre-existing debt.
4. **`.coverage` file stale** (2026-06-16); `fail_under=72` not re-verified this session. Low priority.

## Frozen Phase 0 conclusion *[accepted]*

```text
Build Phase 1 on the current architecture.
Do not recover or migrate historical modules.
Do not rebuild paper synthesis or BibTeX export.
Expose the existing backend capabilities through the product interface.
Track the 136 full-suite failures as test-isolation debt.
Use the recovered paper as a historical workflow fixture, not as a quality oracle.
```

## Decisions required for Phase 1

> **Build Phase 1 entirely on the current architecture.** The lineage reconciliation (0A) found nothing to selectively recover: the nine "missing" capabilities were never implemented as discrete modules in this repo or its pre-Phase-0 parent. The real paper-generation backend (`PaperSynthesizer`) and BibTeX exporter (`BibTeXExporter`) already exist on the current branch — Phase 1's task is to **expose** them in the UI, not to recover them. No migration of historical modules is needed before Phase 1 begins.

**Secondary decision for Phase 1 planning (not blocking):** whether to address the 136 full-suite failures early (improves signal for Phase 1–4 test runs; must separate isolation-defect from genuine-defect hypotheses) or defer to Phase 4. Recommended: defer Phase 1 start is not blocked either way, but the debt must remain tracked until a clean full-suite run is achieved.

---

## Phase 0 completion criteria *[VERIFIED]*

| Criterion | Status |
|---|---|
| Repository lineage classified | ✅ MET — `ERLAB_REPOSITORY_LINEAGE.md` |
| No existing capability scheduled for accidental rebuild | ✅ MET — nothing to recover |
| P0.5 architecture seal green | ✅ MET — 41/41 |
| Fresh backend baseline recorded | ✅ MET — `ERLAB_TEST_BASELINE.md` |
| Fresh frontend baseline recorded | ✅ MET — `ERLAB_TEST_BASELINE.md` |
| Historical pipeline paper recovered | ✅ MET — `historical_baseline/GoT_NSR_Research_Paper.{md,tex}` |
| Stale benchmark pointer disposition completed | ✅ MET (vacuously) — pointer never existed |
| No P1E artifact changed | ✅ MET — only config + snapshot generator + 1 test changed |
| No product feature added | ✅ MET |
| Working tree clean | ✅ MET (at closeout) |

---

## Commit structure *[VERIFIED]*

| # | Hash | Subject |
|---|---|---|
| 1 | `1e10c49` | `docs(project): reconcile ERLab lineage and historical outputs` (0A + 0C) |
| 2 | `433dde7` | `fix(config): restore P0.5 snapshot configuration seal` (0B Step 1) |
| 3 | (tip after closeout) | `docs(project): establish Phase 0 executable baseline` (0B Steps 2–3, 0D, 0E) |

---

*End of Phase 0. No product feature added; no P1E artifact changed; no roadmap proposed beyond the single Phase 1 decision above.*
