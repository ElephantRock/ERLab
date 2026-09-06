# Productive-1 R6 — Diagnostic and Design Tranche

**Status:** diagnostic executed; design drafted; NO implementation. Contract frozen only by owner authorization.
**Authorized objective (owner Decision, R5 adjudication, 2026-08-31):** "Productive-1 R6 diagnostic/design only: determine whether authoritative conclusion-support repair can also be made deterministic and evidence-bound, and design a single shared screening/authority rule. No implementation until that contract is frozen."
**Narrowed successor question (owner):** "Can the pre-existing regr-B conclusion-support defect be repaired deterministically and evidence-safely—by preserving a uniquely justified RESULT mapping where one exists, or otherwise removing/weakening the unsupported empirical assertion—while using exactly the same conclusion-support rule in screening and authoritative evaluation?"
**Method:** entirely offline, on the preserved R5 qualification trial databases (run 33414701494, artifact 9766800703) — the exact rev0/rev1 bytes the qualification produced. Evaluator code verified byte-identical to what qualified (`b9cb75c`). Script and raw results: `r6_diagnostic.py`, `r6_diagnostic_result.json` in this directory. No product code changed.

---

## 1. Diagnostic results

### Q1 — what the authoritative scan actually sees

A stage-faithful reproduction (verbatim extraction and pattern logic from `stages._classify_conclusion`, ~3826–3945) over all four specimens' revision-1 bytes:

| Trial | unmapped claims | mapped claims |
|---|---|---|
| calib-A#1 | 0 | 0 |
| calib-B#2 | 0 | 0 |
| regr-A#1 | 0 | 0 |
| regr-B#1 | **1** | 0 |
| regr-B#2 | **1** | 0 |

regr-B revision 0 carries the same single unmapped claim — the defect pre-exists the repair, as the qualification record showed. The other three specimens have no empirical-assertion pattern matches at all, which is why they passed.

### Q2 — is the claim true, and does a uniquely justified single-marker mapping exist?

The sentence (211 chars, byte-identical rev0→rev1):

> "The results show that rankings are metric-dependent: ridge attains lower RMSE and higher R-squared than Huber at every severity on both datasets, whereas the MAE ranking reverses on both datasets—by severity 0."

Checked against all persisted markers (24 ridge/huber pairs across 2 datasets × 4 severities × 3 metrics):

- **The RMSE/R² sub-claim is TRUE**: ridge's RMSE is lower and R² higher than Huber's in all 16 relevant pairs.
- **The MAE clause is dubious**: MAE ordering favors Huber at airfoil severities 0.25/0.5/0.75 and concrete severity 0.75, and favors ridge at both severity-0 cells — "reverses on both datasets—by severity 0" does not match the recorded ordering cleanly.
- **No single marker uniquely justifies the aggregate claim**: it spans 32 markers (16 pairs). The owner's Option A (a uniquely justified single mapping) does not exist for this sentence; an evidence-set citation is identifiable in principle, but only the RMSE/R² portion verifies.

### Q3 — deterministic removal repair: verified end-to-end

Removing exactly that sentence (one exact span, 211 chars) from regr-B#1's revision-1 bytes:

- Authoritative unmapped claims: **1 → 0**
- Pure gate battery: all green before and after — **zero gate flips**, no new blocking reasons
- Method fidelity: passing before and after
- Structure: RESULT count 112→112, SOURCE count 17→17, heading sequence identical
- Net edit: −211 chars, one span

**Answer to the narrowed question: yes.** Deterministic, evidence-safe repair exists and is verified offline. Removal is the fail-safe form; attachment of backing markers is viable only under a per-sub-claim verification rule (see §3), and this sentence's MAE clause would not survive that rule.

## 2. The shared-rule design (screening ≡ authority)

The diagnostic confirmed **two independent divergences** between the pure screen and the authoritative stage path:

1. **Extraction.** The pure evaluator uses `_extract_abstract`/`_extract_conclusion` (the pure abstract extraction returned 800-character capped text in these trials); the stage does full-section line scanning — uncapped, and treats a "Discussion" heading as part of the conclusion. On blob papers the two extractions see different text.
2. **Classification.** The pure path calls `classify_conclusion_support` and stops. The stage additionally scans the four empirical-assertion patterns ("we demonstrate", "demonstrates that", "experimental results show/indicate", "results show/indicate that"), requires a `[RESULT-N]` within ±200 characters, and forces `overstated` on any unmatched assertion.

**Design:** extract the stage's semantics verbatim into one function — `evaluate_conclusion_support_authoritative(paper_md, result_markers, has_results=None)` in `backend/pipeline/evaluation/conclusion_checker.py` — returning the classification, reason, and the unmapped-claim list. Both `paper_gate_evaluator.evaluate_paper_gates` and `stages._evaluate_paper` call it; neither keeps a private copy. A parity test proves screen ≡ authority on the four preserved rev0/rev1 corpora plus adversarial variants (backed claim, unbacked claim, blob paper, discussion-section claim). This is a product change — implementation only under the frozen R6 contract.

## 3. Deterministic conclusion-repair design (draft)

Same architecture as R5's numeric patcher: derive → apply → postconditions → preservation, one candidate, PAC untouched.

**Repair vocabulary** — sentence-level exact-span patches, two typed forms:

- **R-REMOVE** (fail-safe default): delete the exact span of the assertion sentence. Verified for regr-B. Never fabricates backing; costs the paper one sentence of prose.
- **R-CITE** (conditional): append an evidence-derived marker citation to the sentence — only when a deterministic claim-verification table checks EVERY checkable sub-claim against persisted marker values and all verify (the regr-B RMSE/R² sub-claim verifies; its MAE clause does not, so the whole sentence falls through to R-REMOVE). The verification table is the hard design surface: for comparative claims over `<dataset>.<severity>_<method>_<metric>`-shaped evidence it is expressible deterministically (the diagnostic's Q2 is a worked example); claim shapes outside the table are not repairable by R-CITE and go to R-REMOVE or typed failure.

**Derivation rule (draft):** run the shared authoritative scan on the candidate after numeric patching; every unmapped claim becomes one patch. Decision order: R-CITE if fully verified, else R-REMOVE.

**Postconditions:** R5's carry over (reconstruction byte-proof, heading-sequence identity, no previously-green gate flips, method fidelity preserved) with one refinement — the RESULT marker multiset may change ONLY by exactly the markers attached by R-CITE patches (R-REMOVE changes none); every other constraint is identical.

**Typed failures:** `unverifiable_claim_shape` (R-CITE table has no rule), `removal_blocked_by_gate` (removal flips a previously-green gate — in that case fail closed, persist nothing promotable), plus the R5 applier types.

**Pipeline position:** after numeric patching, before the screen — one candidate revision carries both patch manifests (`numeric_patches` + `conclusion_patches`), persisted in `directive_json`.

## 4. Draft acceptance contract (for the owner to freeze)

Retained from R5: same four frozen specimens × two byte-identical restores; one cold repair per fresh process; ≥7/8 overall and ≥3/4 per family; negative control blocked; zero false promotions; zero operator edits; scope integrity binding; E == F == R == H on every ready trial; evidence completeness (trial DBs, logs, manifests, response bodies); 600s = authoritative-evaluation ceiling, timeout an ordinary failed trial, no carve-out, no same-contract rerun.

Added for R6:

1. **Shared-rule parity:** screening and authoritative evaluation call the same conclusion-support function; a parity test over the four preserved corpora plus adversarial variants is part of the candidate's suite.
2. **Conclusion patch accounting:** every trial's evidence includes the conclusion patch manifest (typed R-REMOVE/R-CITE, exact spans, verification table outputs).
3. **No fabricated backing:** R-CITE may attach only markers whose persisted values the verification table checked; any unverifiable sub-claim forces R-REMOVE or fail-closed.
4. **Preservation set:** no previously-green gate may flip (R5's P4), now including the shared-rule conclusion gate itself.
5. **Marker-delta rule:** RESULT multiset delta = exactly the R-CITE attachments; SOURCE multiset unchanged.

**Expected decisive trial:** regr-B — the only state with a conclusion defect; if R-REMOVE/R-CITE behave as verified offline, the family minimums are reachable mechanically. That is also the honest caveat: the diagnostic verified one sentence on one specimen; the qualification still has to demonstrate it under the frozen contract.

## 5. Open decisions for the owner

1. Include R-CITE in R6, or R-REMOVE-only first (R-CITE's verification table is the widest new surface; R-REMOVE alone already unblocks regr-B)?
2. Same four specimens (regr-B now decisive) — confirm, given the no-post-hoc-change principle applies to R5's contract, not R6's new one.
3. Whether a removed sentence's information loss (the paper loses its summary claim) is acceptable product behavior, or whether R-CITE should be prioritized to preserve content.

## 6. What this tranche did NOT do

- No product code written or changed; no branch, PR, or remote state touched.
- R-CITE's verification table is designed, not implemented — only its Q2 worked example exists.
- The removal repair is verified on regr-B#1's bytes; regr-B#2 was scan-verified identical, not battery-re-run.
- No qualification harness was built or run.
