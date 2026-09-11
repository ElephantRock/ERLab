# Productive-1 R5 — Frozen Charter (owner-approved 2026-08-31)

Provenance: the owner approved the R5 freeze following the design tranche
(`r5_design_tranche.md` in this directory). The operative freeze text is
recorded verbatim below. This file is the charter of record for the R5
candidate branch; changes require owner authorization.

---

**Objective:** Replace Productive-1 automatic numeric repair with a deterministic, evidence-derived exact-span patch pipeline. For every numeric-fidelity mismatch, derive the authorized numeric token span and required replacement directly from persisted RESULT evidence; apply only those patches; prove byte identity outside authorized spans; preserve all previously passing gates and document structure; then hand the candidate unchanged to the existing PAC authoritative evaluation/promotion path.

**Frozen product constraints:** no repair-side LLM call; no retry loop; no experiment rerun; no DB migration; no new or weakened evaluator gate; no threshold change; no fabricated marker/evidence mapping; no heading creation/deletion; no SOURCE/RESULT identity mutation; PAC remains sole promotion authority; freeze/release semantics remain unchanged.

**Deterministic acceptance controls:** exact manifest ↔ source-span provenance; every replacement lexically resolves to the persisted RESULT value; reconstruction proves all bytes outside patch spans identical; all previously passing method-fidelity facts remain passing; section-heading sequence identical; RESULT/SOURCE marker identities and counts identical; malformed/ambiguous/overlapping patches fail closed with typed reasons; production `EvidenceInvariant` passes using the real session-derived construction.

**Qualification contract:** same four frozen specimens × two byte-identical restores; one cold automatic repair per fresh process; no operator edits or continuation decisions; same negative control; same provider/model for authoritative evaluation; **≥7/8 overall, ≥3/4 per family**; zero false promotions; scope integrity mandatory; complete rev0/rev1 gate state, patch manifest, reconstruction proof, provider/server logs, and exact failure reason captured; `E == F == R == H` for every successful ready trial.

**Timeout policy:** deterministic repair itself has no model deadline; retain **600 seconds as the authoritative evaluation/provider ceiling**, with timeout counting as a failed trial and no environmental carve-out.

**Resolved load-bearing decisions (owner, with the freeze):**

1. **Deterministic-patch-only for R5.** Do not include a linguistic repair model path in this successor. The qualification defects are all numeric and already have authoritative persisted replacement values. Adding an LLM would add latency, nondeterminism, formatting failures, and a preservation surface without solving a demonstrated R5 requirement. Linguistic repair can be a later separately justified capability.
2. **Make scope integrity binding.** R4 proved that recording it as an observation is insufficient. R5 should fail qualification—and fail the individual repair candidate—if reconstruction shows any byte outside authorized spans changed, if a heading is created/deleted, or if marker identity changes.
3. **Retain the 600-second ceiling, but explicitly classify it as an authoritative evaluation/provider deadline, not a repair-generation budget.** Deterministic patch application should have no meaningful model-scale timeout. This keeps the operational reliability requirement without pretending that R5's repair itself needs 600 seconds.

Owner ruling on the tranche boundary: "the next authorized tranche is implementation of exactly this deterministic patch path—nothing broader." → **Approved.**
