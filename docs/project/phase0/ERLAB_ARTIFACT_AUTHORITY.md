# ERLab Artifact Authority Cleanup

> **Phase 0 — Work Package 0D.**
> **Purpose:** remove ambiguity about which benchmark and product artifacts are authoritative.
> **Baseline HEAD:** `d5990bc4e603767dc1282a7044122ed5e9be8ea5`.

---

## Correction to the prior current-state report *[VERIFIED]*

The current-state report (`docs/project/ERLAB_CURRENT_STATE_REPORT.md` Part 1 and the inventory JSON) listed `benchmarks/latest.json` as a **stale** artifact referencing 65 deleted pre-wipe runs. **This was incorrect.** Phase 0 verification establishes:

| Check | Result |
|---|---|
| Does `benchmarks/latest.json` exist on disk? | **NO** — `head: cannot open 'benchmarks/latest.json': No such file or directory` |
| Does `benchmarks/` directory exist on disk? | **NO** — `benchmarks/ does NOT exist on disk` |
| Is `benchmarks/` in the HEAD tree? | **NO** — `git ls-tree HEAD --name-only \| grep benchmarks` returns nothing |
| Is `benchmarks/` in any commit of this repo (all branches)? | **NO** — `git log --all --oneline -- "benchmarks/"` returns nothing |
| Is `benchmarks/` in the pre-Phase-0 platform repo (`origin/master`)? | **NO** |
| Are there any consumers of `benchmarks/latest.json` in code? | **NO** — `grep -rn "benchmarks/latest\|latest.json" backend/ scripts/ frontend/src/` (excluding tests/node_modules) returns nothing |

**Conclusion:** the `benchmarks/latest.json` entry in the prior report was a phantom — it does not exist anywhere in this repository's history, working tree, or the pre-Phase-0 parent repo, and no code consumes it. The prior report's top-level directory listing must have been read from a different/stale source.

**Disposition:** **no action required.** There is nothing to supersede or remove. The stale-pointer risk the work package was designed to address does not exist in the current repository.

> **Honesty note:** The current-state report (commit `d5990bc`) over-claimed this artifact's presence. Phase 0 corrects the record. The inventory JSON (`docs/project/erlab_current_state_inventory.json`) `stale_benchmarks_latest_json` entry should be read as RESOLVED-NOT-APPLICABLE, not as an open item.

---

## Authoritative retrieval lineage *[VERIFIED]*

With the phantom disposed of, the actual authoritative benchmark lineage is unambiguous and entirely under `data/evaluation/` + `docs/research/` + `docs/p1b_snapshot/`:

| Layer | Path(s) | Status |
|---|---|---|
| P1B frozen snapshot (control) | `docs/p1b_snapshot/snapshot.json` (10.8 MB; gitignored, regenerable via `python -m backend.ranking.generate_embedding_snapshot`), `docs/p1b_snapshot/MANIFEST.md`, `.fingerprint` sidecar | AUTHORITATIVE — frozen control; P1B closeout `2d8b26f7…` |
| P1B blind-adjudication packages | `docs/p1b_gate1/`, `docs/p1b_gate2/` | AUTHORITATIVE — sealed |
| P1E.0 audit artifacts | `data/evaluation/p1e_frozen_split_manifest.json`, `p1e_case_diagnostics.json`, `p1e_discrimination_audit.json`, `p1e_policy_pairwise_comparison.json`; `docs/research/p1e_benchmark_discrimination_audit.{md,json}`, `p1e_benchmark_discrimination_audit_protocol.md` | AUTHORITATIVE — Outcome M, commit chain `2032579`→`063d060` + `c1fa554` |
| P1E.1 sealed benchmark-extension artifacts | `data/evaluation/p1e1_*` (16 files: split manifest, candidate package/provenance/mining, caldev adjudication, blind held-out package, adjudication/construction provenance, custody receipt, diagnosis, prejudgment diagnostics); `docs/research/p1e1_benchmark_extension.md`, `p1e1_benchmark_extension_protocol_v4.md` (effective) | AUTHORITATIVE — corpus + cal/dev sealed; commit chain `d2e16ae`→`cea3ea1` |
| P1E.2 (held-out adjudication) | — | **NOT YET COMPLETED** (blocked on custody prerequisites) |
| P1E.3 (frozen policy comparison) | — | **NOT YET COMPLETED** (blocked on P1E.2) |

**No active code path silently treats a deleted-run benchmark pointer as current**, because no such pointer exists.

---

## Exit condition *[VERIFIED]*

> No active code path can silently treat the deleted-run benchmark pointer as the current benchmark.

**MET — vacuously.** The pointer does not exist in the repository. No disposition (supersede/remove/update-consumer) was needed. The authoritative retrieval lineage is recorded above.

---

*End of Work Package 0D. Investigation only; no artifact modified.*
