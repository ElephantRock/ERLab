# Productive-1 R5 — Diagnostic and Successor Design Tranche

**Status:** design tranche executed; NO implementation. Frozen objective/acceptance contract pending owner authorization.
**Authorized objective (owner, 2026-08-30):** "Productive-1 R5 diagnostic and successor design: evaluate exact-span deterministic/structured-patch repair as the replacement for section regeneration; no implementation until the R5 objective and acceptance contract are frozen."
**Baseline:** R4 TERMINAL (FAILED / NOT QUALIFIED 3/8, consumed, run 33286261653). Two demonstrated candidate defects: (1) scoped section rewrite of a single-blob abstract destroyed already-passing method-fidelity compliance on all four regression trials; (2) a scoped replacement introduced a new results section that revision 0 never had (calib-B#2).
**Product code touched by this tranche:** none. Everything here ran offline against main (`ea156f3`) — the validator, gate, parser, and method-fidelity modules are byte-identical between main and the R4 candidate (`98b7853`), verified by diff.

---

## 1. The diagnostic question

The owner froze one architectural question before implementation: **how much repair must remain model-generated?** For the demonstrated numeric defects the required values are already persisted. The diagnostic tests, against all four frozen qualification specimens, whether deterministic exact-span patches alone can take each revision-0 state to a fully green gate set — with every preservation property the R4 mechanism lacked.

## 2. Method

For each frozen specimen (`calib-A_runfail3.db`, `calib-B_runfail2.db`, `regr-A_case3a.db`, `regr-B_3E_era.db` — all four SHA-256s match the R4 trial records):

1. Rebuild the marker set from persisted evidence (the qualification harness's own reconstruction).
2. Run the production validator (`validate_claim_result_alignment`) on revision 0 — the same function the route's gates use.
3. Build deterministic patches with the validator's own adjacency regexes (`_NUM_BEFORE_RE`, `_NUM_AFTER_RE`): every number token rendered adjacent to a marker whose float value disagrees with the persisted `observed_value` beyond the 1e-6 tolerance is replaced, in place, by `repr(observed_value)` (shortest exact round-trip rendering; agreement holds by construction).
4. Apply the patches as exact span replacements (asserted non-drifting).
5. Re-run the full battery on the patched paper: the validator, `evaluate_method_fidelity` with the frozen facts, the pure gate evaluator, the section parser, marker counts, and byte accounting.

Script and raw results: `r5_diagnostic.py`, `r5_diagnostic_result.json` in this directory.

## 3. Results

| Specimen | rev0 numeric mismatches | deterministic patches | mismatches after | method_fidelity after | pure gates after | sections / markers | net chars changed |
|---|---|---|---|---|---|---|---|
| calib-A | 6 | 6 | 0 | pass (was pass) | all green, zero blocking | names+headings identical; RESULT/SOURCE counts identical | 10 |
| calib-B | 13 | 13 | 0 | pass (was pass) | all green, zero blocking | identical | 26 |
| regr-A | 10 | 10 | 0 | pass (was pass) | all green, zero blocking | identical | 15 |
| regr-B | 8 | 8 | 0 | pass (was pass) | all green, zero blocking | identical | 13 |

Observed defect shapes, all patched deterministically: decimal shifts (`742593` → `3.742593`), sign flips (`0.006701` → `-0.006701`), wrong values (`0.215127` → `0.196669`), percent-scale integers (`333333` → `0.333333`), and malformed renderings (`05` → `0.05`). Multiple defective renderings of the same marker (e.g., `[RESULT-26]` three times in regr-A) are each patched individually; already-correct renderings are left untouched.

**Answer to the architectural question: for the four frozen qualification states, repair-side model calls needed = 0.** Every mismatch the R3 and R4 qualifications were fighting is span-addressable from persisted evidence.

Two precisions keep this honest:

- **The authoritative evaluation still makes one provider call per trial.** `_evaluate_paper` invokes the `ProposalEvaluator` for dimension scores; a thrown exception yields `status="failed"`, and dimension scores never gate (stages.py: "a blocking gate prevents an unqualified positive state. The dimension scores remain visible as subordinate diagnostics but cannot override the gate"). That call worked in all eight R4 trials. R5 is model-free on the repair side only; the qualification still needs a live provider for evaluation.
- **The scratch invariant check could not be reproduced offline.** `verify_revised_paper_invariants` reports "invented RESULT markers" on the **unpatched** revision 0 as well, because my scratch `EvidenceInvariant` construction differs from the remediator's session-derived one. This is a harness artifact of this diagnostic, not a property of the patches (the patches change no markers, proven by counts and section identity). The production applier must run the real invariant check with the remediator's evidence construction — that is implementation work, listed in §5.

## 4. Why this defeats both R4 defects by construction

- **Preservation:** the patch replaces number tokens only. Methodology statements, headings, and every other byte are untouched — a 3,000-word single-blob "abstract" is no longer an editing unit, so there is no regeneration that can drop frozen method facts. As a belt-and-braces rule (not just an emergent property), the applier must re-run every gate that passed before repair and reject the candidate if any flips (§5, P4).
- **Structural containment:** patches cannot introduce headings, sections, or markers — the edit vocabulary is "replace this exact number token with that exact number token." A new `## Results` section is unrepresentable.

## 5. Design (for the R5 implementation tranche — not started)

**Patch manifest (deterministic path).** Each repair produces a manifest, persisted with the revision:

```json
{"patches": [
   {"marker": "[RESULT-7]", "span_start": 12345, "span_end": 12352,
    "old_text": "742593", "new_text": "3.742593",
    "required_value": 3.742593, "metric_name": "airfoil_self_noise.0_25_huber_mae",
    "artifact_sha256": "…", "basis": "persisted observed_value"}
 ]}
```

**Applier rules (all fail-closed, typed):**

- **P1 span validity:** `paper[span_start:span_end] == old_text`, else `patch_span_drift` — reject.
- **P2 span provenance:** every span must be derived from the validator's adjacency regexes against a marker in the frozen map, else `patch_span_unauthorized` — reject. Nothing outside authorized spans may differ (assert by reconstruction).
- **P3 lexical containment:** `new_text` must be a rendering of the persisted value that the validator's own comparison accepts (`float(new_text)` within 1e-6), else `patch_value_invalid`. The patcher emits `repr(value)`; any other rendering must be justified the same way.
- **P4 preservation postconditions:** after application, re-run every gate that passed pre-repair (including `method_fidelity` with frozen facts) plus the invariants check with the remediator's real evidence construction. Any flip → `preservation_violation` — reject, persist nothing promotable. This converts R4's emergent disaster into a checked contract.
- **P5 structural freeze:** marker token multiset and parsed section names/headings must be identical before and after, else `structural_change` — reject.
- **P6 typed failures:** each rejection carries its type in the API response and the persisted trigger detail — no branch-elimination forensics.

**Model-path policy (the owner's reserved scope).** Deterministic patches handle defects derivable from persisted evidence. Defects that are genuinely linguistic — `conclusion_support` overstated, `scope` off-scope — have no persisted-value derivation and remain the only candidates for a model call. If the owner keeps a model path at all in R5, it must emit the same patch-manifest format (model proposes spans; the deterministic applier validates and applies under P1–P6). Note the R3 evidence: prompt-rule compliance for conclusion_support was 1-for-2 on completed revisions — a model path should not be assumed reliable, and the frozen four states need none.

**Integration seam.** The patcher replaces the generation call inside `auto_revise_paper` (candidate producer). Everything downstream is untouched and stays authoritative: revision persistence, the route's authoritative evaluation of persisted revision-1 bytes, PAC's locked reads, identity assertions, and CAS promotion. `E == F == R == H` verification unchanged.

**Evidence capture (fixing the R3/R4 gap).** Qualification evidence must include, per trial: the exact patch manifest, the patched revision bytes (or their hash plus the manifest, from which bytes reconstruct deterministically), the API response body, per-trial API server logs, and timing. No more `.tmp` glob misses.

## 6. Draft acceptance contract (for the owner to freeze)

Retained from R4 verbatim: four frozen specimens × two byte-identical restores each; ≥7/8 overall; ≥3/4 per family; the negative control (unmodeled percent transform) stays blocked; 600-second per-trial ceiling; no retries, no experiment reruns; PAC sole promotion authority; `E == F == R == H` on every ready promotion; zero operator edits or continuation decisions.

Added, per the R4 lessons and this diagnostic:

1. **Exact edit-span accounting:** every trial's evidence includes the patch manifest; total changed characters expected ≤ ~30 per specimen (10–26 observed).
2. **No heading creation or deletion:** parsed section names and headings byte-identical before/after (P5).
3. **Method-fidelity preservation:** every method-fidelity fact that passed at revision 0 must still pass at revision 1 (P4) — this is now an explicit acceptance condition, not an emergent hope.
4. **Unchanged bytes outside authorized patches:** verified by reconstruction from the manifest (P2).
5. **Typed malformed-patch failure:** if the patcher or applier rejects, the response carries the typed reason (P6); a rejection is a failed trial, not a retry.
6. **Evidence completeness:** per-trial response bodies, patch manifests, revision hashes, API logs, and timings preserved in the artifact (no upload-glob gaps).
7. **Scope-integrity as a wired condition:** if the owner intends structural containment as an acceptance criterion (recommended given calib-B#2), it must appear in the harness's `pass` predicate at freeze time — R4 recorded it as observation only.

**Expected failure surface under this contract:** with generation removed, the remaining per-trial risks are the evaluation-side provider call and freeze/release orchestration — environmental, not generative. That is the point: R5 qualifies preservation and orchestration deterministically, and any failure will be precisely attributable.

## 7. Open decisions for the owner (freeze before implementation)

1. Does R5 include a model path for linguistic defects at all, or is it deterministic-patch-only for this contract (the four frozen states need no model; a separate successor can add the linguistic path under its own qualification)?
2. Is scope-integrity (structural containment) a pass-gating acceptance condition or observation-only? (Recommendation: pass-gating, per §6.7.)
3. The 600-second ceiling is now nearly vacuous for repair (patches are local); it effectively bounds the evaluation call. Keep as-is or re-scope explicitly to the evaluation/provider budget?

## 8. What this tranche did NOT do

- No product code was written or changed; no branch, PR, or remote state was touched.
- The invariant-check discrepancy (§3) was isolated but not root-caused — reproducing the remediator's evidence construction is implementation-tranche work.
- The negative control was not re-executed (the validator is untouched, so its behavior is unchanged by inspection, not by test).
- The evaluation-side provider dependency is characterized from code and R4 trial evidence, not by a live call in this tranche.
