# ERLab Repository-Lineage Reconciliation

> **Phase 0 — Work Package 0A.**
> **Purpose:** determine whether earlier ERLab capabilities were deleted, moved, renamed, left on another branch, developed in another repository, or described in reports without reaching this codebase. Prevent accidental rebuild of work that already exists somewhere.
> **Method:** investigation only. No code was ported, merged, or rewritten.
> **Baseline HEAD:** `d5990bc4e603767dc1282a7044122ed5e9be8ea5` on `feat/quarantine-and-frontend-redesign`.

---

## Repository topology *[VERIFIED]*

| Repo / ref | HEAD | Role | Commits |
|---|---|---|---|
| `C:\Next-Era\Elephant-Rock-Research-Lab` @ `feat/quarantine-and-frontend-redesign` | `d5990bc4…` | Current development branch | — |
| `C:\Next-Era\Elephant-Rock-Research-Lab` @ local `master` | `78821e6f…` (2026-07-01, "chore: stop tracking .env") | Strict ancestor of feat | — |
| `origin` → `C:\Next-Era\elephant-rock-platform` @ `origin/master` | `c275c6d9…` (2026-06-07, "feat: LM Studio Manager v2") | **Pre-Phase-0 repository** | 529 |
| Phase 0 wipe commit | `e2c0171d…` (2026-06-16) | "Clean migration baseline" — deleted 1,573 files | parent = `c275c6d` (platform HEAD) |

**Ancestry (VERIFIED via `git merge-base --is-ancestor`):**
```
origin/master (c275c6d, platform HEAD)
   └── 76 commits → local master (78821e6)
                      └── 233 commits → feat HEAD (d5990bc4)
```

**Both `master` and `origin/master` are strict ancestors of `feat`.** Nothing lives on either master that isn't on feat. `git rev-list --count HEAD..master` = 0 and `HEAD..origin/master` = 0.

**Consequence:** any capability absent from the `feat` working tree is *also* absent from both masters. The only other place capabilities could plausibly live is the external pre-Phase-0 repo — and they are not there either (verified below).

---

## The `erlab/` package does not exist as code *[VERIFIED]*

Searched via `ls-tree`, `find -type d -name erlab`, and filename grep in **both** repos. There is **no `erlab/` directory or Python package anywhere** — not on disk, not in any git tree, not on any branch/tag, not deleted in any commit.

The token `erlab` appears only as a **documentation label**: `docs/project/ERLAB_*.md` and `erlab_current_state_inventory.json`. "ERLab" is the project's product name, not a Python package. The task's reference to "the earlier `erlab/` package" is not matchable to any code artifact in either repository's history.

---

## Method *[VERIFIED]*

For each capability: `git log --all --grep` (current + external), `git log --all --diff-filter=D` path searches, `git log -S` pickaxe on class names (PascalCase), `git ls-tree -r` filename grep on `master`/`origin/master`, working-tree `grep -r` of identifiers in `backend/**/*.py`, and `find` for module filenames. Pickaxe ran across **all history of both repos (838 + 529 = 1367 commits)** and returned essentially nothing for the PascalCase class names.

---

## Capability classification matrix *[VERIFIED]*

Status legend: `CURRENT` · `PRESENT_UNWIRED` · `OTHER_BRANCH` · `DELETED_RECOVERABLE` · `EXTERNAL_REPOSITORY` · `DOCUMENTED_ONLY` · `UNKNOWN`.

| Capability | Historical evidence | Current location | Git location | Status | Recommended disposition |
|---|---|---|---|---|---|
| `evidence_table` (research) | Capability matrix row #9 = MISSING; no research-evidence-table module ever committed in either repo (pickaxe empty) | none | none (838+529 commits) | **DOCUMENTED_ONLY** | leave historical — never existed |
| `evidence_table` (model-certification) | `backend/pipeline/model_certification/scorers/evidence_table.py` — a *scorer* for certifying embedding models, NOT research evidence | `backend/pipeline/model_certification/scorers/evidence_table.py` (HEAD) | identical in both repos; never deleted | **CURRENT** (different scope; excluded category) | preserve current — not the research capability |
| `evidence_packet` | Zero hits across all history of both repos: no commit message, no path, no `EvidencePacket` pickaxe hit, no filename | none | none | **DOCUMENTED_ONLY** | leave historical — never existed |
| `argument_coherence` | String appears only as a *metric key* in `backend/pipeline/model_certification/scorers/synthesis.py:3,67` (`"argument_coherence": round(coherence, 3)`). No `ArgumentCoherence` class/module ever existed (pickaxe empty) | metric key only | identical in both repos | **DOCUMENTED_ONLY** (token collision) | leave historical — never a discrete capability |
| `multi_paper_synthesis` | No module, no `MultiPaperSynthesis` class (pickaxe empty both repos). `git log --grep` hits are exclusively P1D.2 diagnostic-seed commits (`d36ccaf`, `72aa05f`) — explicitly excluded | none | none | **DOCUMENTED_ONLY** | leave historical — closest real code is single-run `synthesis/{proposal,section_wise,fast,paper}_synthesizer.py` (row #13 WORKING) |
| `external_validation` | No external-reviewer capability. `git log --grep`, path search, `ExternalValidation` pickaxe all empty in both repos. Closest code is `backend/pipeline/verification/` (citation/provenance) — internal-only | none (internal `verification/` exists) | none external | **DOCUMENTED_ONLY** (internal `verification/` is PRESENT_UNWIRED) | leave historical — would be net-new build |
| `bibliography` | No `bibliography` module. **Real capability exists under a different name:** `BibTeXExporter` at `backend/pipeline/export/bibtex_exporter.py` (`paper_to_bibtex`, `papers_to_bibtex`, `proposal_to_bibtex`) — capability matrix row #17 = WORKING, exposed via `/runs/:id` BibTeX button | `backend/pipeline/export/bibtex_exporter.py` (HEAD) | identical in both repos; `639e1a4` "BibTeX export for papers and proposals" | **CURRENT** (different name) | preserve current — exists as `bibtex_export` |
| `paper_draft` | The ONLY `PaperDraft` token in all history is commit `cc8694e` (2026-05-09) — **roadmap planning text** in `sessions/260501-ivory-wolf/data/pdf_to_paper_roadmap_study.md` (free-form markdown), itself deleted in Phase 0 wipe. No `PaperDraft` class/module ever existed. Real capability: `PaperSynthesizer` + `PaperSynthesisStage` | `backend/pipeline/synthesis/paper_synthesizer.py` (HEAD, row #15) | planning doc deleted at `e2c0171`; synthesizer preserved | **CURRENT** (different name; planning doc DELETED) | preserve current — `paper_synthesizer` is the real capability; NOT exposed in UI |
| `release_manifest` | No `release_manifest` module or `ReleaseManifest` class (pickaxe empty both repos). Only `manifest` code is `backend/pipeline/model_certification/manifest.py` (candidate-model manifest, unrelated) | none | none | **DOCUMENTED_ONLY** | leave historical — never existed |
| `audit_seal` | No `audit_seal` module or `AuditSeal` class anywhere. Only reference is `erlab_current_state_inventory.json:300` listing architecture-invariant seal *test* files (`backend/tests/architecture/test_p0_4_*_seal.py`, `test_p0_5_seal.py`) — all exist at HEAD | architecture-seal tests at HEAD | architecture tests on feat only (post-Phase-0 governance) | **CURRENT** (different referent) | preserve current — these are ratchet tests, not a product capability |

---

## Summary by fate *[VERIFIED]*

| Fate | Capabilities |
|---|---|
| **CURRENT (exists at HEAD, different name)** | `bibliography`→`bibtex_export`; `paper_draft`→`paper_synthesizer` (NOT exposed in UI); `audit_seal`→architecture-seal tests |
| **DOCUMENTED_ONLY / never existed as discrete capability** | `evidence_table` (research), `evidence_packet`, `argument_coherence`, `multi_paper_synthesis`, `external_validation`, `release_manifest` |
| **DELETED_RECOVERABLE** | **None of the nine.** No capability module was ever deleted. The Phase 0 wipe (`e2c0171`) deleted runtime artifacts, session papers, design drafts, and ONE source file — `backend/pipeline/orchestrator.py` — which was **refactored into the `backend/pipeline/orchestrator/` package** (logic preserved, not lost) |
| **OTHER_BRANCH** | **None.** Both `master` and `origin/master` are strict ancestors of `feat` |
| **EXTERNAL_REPOSITORY** | **None.** Pickaxe + tree search of `C:\Next-Era\elephant-rock-platform` (origin/master, 529 commits) return identical empty results |
| **PRESENT_UNWIRED** | `external_validation` is the closest — internal `verification/` exists but no external-reviewer path |

---

## The single substantive deletion: `orchestrator.py` *[VERIFIED]*

| Aspect | Platform (`origin/master`) | Research-Lab (HEAD) |
|---|---|---|
| Path | `backend/pipeline/orchestrator.py` | (deleted; replaced by package) |
| Size | 120,490-byte monolith | — |
| Replacement | — | `backend/pipeline/orchestrator/` package: `_orchestrator.py` (59,775 B) + `composition_root.py`, `decision_gate.py`, `result_processor.py`, `run_coordinator.py`, `service_registry.py`, `stage_executor.py`, `stage_lifecycle.py` (~194 KB total) |
| Verdict | Refactor/decomposition, **not a capability loss** | Logic preserved and split |

> Filtering all 1,573 Phase-0 deletions to `backend/**.py` (non-test) yields **only** `orchestrator.py`. **No source-capability module from the platform is missing from Research-Lab.**

---

## Conclusion *[VERIFIED]*

**No accidental rebuild risk exists from deleted or relocated modules.** The current branch's report (capability matrix rows #7–#12, #19, #22) that these capabilities are MISSING or NOT_EXPOSED is **correct**. Specifically:

1. The `erlab/` package never existed as code in either repository.
2. Six of the nine queried capabilities (`evidence_table` research, `evidence_packet`, `argument_coherence`, `multi_paper_synthesis`, `external_validation`, `release_manifest`) were **never implemented** in this repo or its pre-Phase-0 parent. Any future build of these is genuinely net-new work, not a rebuild.
3. Three (`bibliography`, `paper_draft`, `audit_seal`) have **closely-related real artifacts under different names** that are already tracked in the capability matrix (`bibtex_export` = WORKING; `paper_synthesizer` = NOT_EXPOSED in UI; architecture-seal tests = the actual `audit_seal` referent).
4. The only deleted source file (`orchestrator.py`) was a **refactor into a package**, not a capability loss.
5. The pre-Phase-0 repo (`elephant-rock-platform`) is a **strict ancestor** of the current branch — it contains nothing the current branch lacks (modulo the 1,573 runtime/design deletions, none of which are source capabilities).

### Decision produced for Phase 1

> **Build Phase 1 entirely on the current architecture.** There is nothing to selectively recover. The capabilities that earlier project history described but the current branch lacks were never implemented as discrete modules in this repository or its pre-Phase-0 parent; they would be net-new work, not a migration. The real paper-generation backend (`PaperSynthesizer`) and BibTeX exporter (`BibTeXExporter`) already exist on the current branch — the Phase 1 task is to **expose** them in the UI, not to recover them.

---

*End of Work Package 0A. Investigation only; no repository source or product artifact modified.*
