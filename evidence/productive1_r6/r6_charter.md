# Productive-1 R6 — Frozen Charter (owner-frozen 2026-08-31)

Provenance: the owner froze the R6 successor contract following the R6 design
tranche (`r6_design_tranche.md` in this directory). The operative freeze text is
recorded verbatim below. Implementation is a separate authorization point;
nothing in this file authorizes implementation.

---

### Frozen R6 objective

**Align screening and authoritative conclusion-support semantics behind one shared deterministic rule, and extend the existing exact-span repair pipeline with deterministic removal of unsupported empirical assertion sentences. No repair-side model calls.**

### Frozen product constraints

* No LLM/provider call in repair.
* No R-CITE capability.
* No fabricated RESULT/SOURCE mapping.
* No evaluator threshold change.
* No DB migration.
* No experiment rerun.
* No retry-until-pass behavior.
* PAC remains sole promotion authority.
* Existing freeze/release semantics remain unchanged.
* Authoritative conclusion-support semantics must not be weakened; the shared function must reproduce the current stage behavior.

### Frozen repair semantics

The shared conclusion-support function must use one extraction implementation and one empirical-claim rule for both screening and authoritative evaluation. The current authoritative four-pattern scan and RESULT-backing requirement become the canonical semantics.

For an unmapped empirical assertion, R6 may produce one **R-REMOVE** patch covering exactly the complete sentence containing the matched assertion. The sentence must contain no RESULT or SOURCE marker. Patch spans must be derived against the original revision, must not overlap numeric patches, and the deterministic applier must reject drift, ambiguity, overlap, or structural mutation with typed failure reasons.

Bytes outside authorized numeric spans and authorized R-REMOVE spans must reconstruct exactly.

### Deterministic acceptance controls

Before qualification, tests must prove:

* shared screening/authority classification parity on all preserved specimens and preserved R5 trial revisions;
* regr-B rev0 and rev1 each expose exactly the demonstrated unsupported assertion;
* calib-A, calib-B, and regr-A expose no new removal target;
* exact R-REMOVE on both preserved regr-B revisions yields zero unmapped empirical assertions;
* numeric mismatches remain zero after combined repair;
* every previously passing gate remains passing;
* method fidelity remains passing;
* heading sequence is identical;
* RESULT/SOURCE marker multiset is identical;
* reconstruction proves byte identity outside authorized spans;
* already-backed empirical claims remain byte-identical;
* ambiguous/malformed sentence boundaries, marker-bearing target sentences, overlapping patches, span drift, or postcondition regression fail closed with typed reasons;
* zero repair-side provider construction is possible.

### Qualification contract

Retain the R5 qualification structure:

**4 frozen specimens × 2 restores = 8 trials**, one cold repair each, same authoritative evaluation provider/model, ≥7/8 overall, ≥3/4 per family, zero negative-control promotions, zero operator edits/continuation decisions, no timeout carve-out, binding scope integrity, and `E == F == R == H` for every ready result.

Add R6-specific evidence per trial: canonical shared-rule extraction, detected empirical assertion spans, R-REMOVE manifest, exact removed sentence hash/text, pre/post conclusion-support classification, patch reconstruction proof, and preserved server/provider logs.

R6 qualification should additionally require **zero screening/authority conclusion-support disagreement** on all eight trials.

---

**Owner's resolved design decisions (with the freeze):**

1. **R6 is R-REMOVE-only.** No citation synthesis or marker attachment. An empirical assertion caught by the shared authoritative rule and lacking required RESULT backing may only be removed exactly; it may not be paraphrased, weakened by an LLM, or decorated with evidence.
2. **Keep the same four frozen specimens × two restores.** Regr-B proves the new capability; calib-A/B and regr-A remain regression controls. Do not replace or "clean" the specimen set after observing R5.
3. **Sentence-removal information loss is acceptable under this contract.** The governing rule is evidence support, not preservation of unsupported prose. Removal is allowed only for the exact assertion sentence identified by the shared rule, only when it lacks required RESULT backing, and only if all preservation postconditions remain green. A true-but-unbacked assertion is still non-authoritative under the existing evaluator contract.

Owner's boundary ruling: "That contract is now frozen. **Implementation is a separate authorization point; no R6 implementation should begin unless you explicitly authorize it.**"
