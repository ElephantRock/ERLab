# Case-3 Gate-Chain Erratum: G0 transcription error in sealed manifests

Recorded 2026-08-17, per owner review of the 3E evidence package.
The sealed manifests are preserved byte-exact; this erratum corrects
the record without touching them.

## The error

The canonical Case-3 baseline, as frozen in
`evidence/case3_architecture_manifest.json` and used by every merged
gate PR, is:

```
G0 = d70d7046c3868ba6fb73d8f4d2a132c48feeca
```

The qualification-attempt manifests **case3b_manifest.json,
case3c_manifest.json, and case3d_manifest.json** carry a transcribed
variant of this value (`…ba6fbaf73d8f…` in place of `…ba6fb73d8f…` —
two characters displaced). The error was introduced when the 3B
manifest was first built and propagated by copy to 3C and 3D.
**case3e_manifest.json carries the canonical value** — the 3E manifest
was rebuilt from the canonical source rather than copied.

## Ruling

- The sealed manifests (3B/3C/3D) are **not edited**: their SHA-256
  seals bind the bytes as preregistered, and a post-hoc byte change
  would break the very integrity the seals protect.
- The transcribed value is a **provenance-labeling error only**. It
  never influenced any code, gate, or run: every commit-level
  decision keyed on the actual git history (PR #20 → `7bfbd1a` = G1;
  PR #24 → `a057982` = Q0; PR #29 → `00c1050` = Q1; PR #34 →
  `afa58e4` = Q2), and the pipeline never consumed the manifest's
  gate-chain labels.
- The authoritative gate chain is the one recorded here and in
  `evidence/case3_architecture_manifest.json` / the 3E acceptance
  record.
