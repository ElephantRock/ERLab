# Case-3 G0 Erratum v2: the first erratum inverted the error direction

Recorded 2026-08-19, per owner review of the Case-3 evidence package.
This erratum supersedes the error-direction claims of
`evidence/case3_gate_chain_erratum.md` (2026-08-17). The sealed manifests
are preserved byte-exact throughout; nothing sealed is edited.

## The authoritative G0

The canonical Case-3 baseline, as frozen in
`evidence/case3_architecture_manifest.json` (`baseline.G0`) and as used by
every merged gate PR, is:

```
G0 = d70d7046c3868ba6fbaf73d8f4d2a132c48feeca
```

`git rev-parse d70d7046c3868ba6fbaf73d8f4d2a132c48feeca` resolves this
40-character value to a real commit. The variant below does not resolve
in git history at all.

## What each artifact actually carries (verified 2026-08-19)

| Artifact | G0 value recorded | Status |
| --- | --- | --- |
| `evidence/case3_architecture_manifest.json` | `d70d7046c3868ba6fbaf73d8f4d2a132c48feeca` | canonical, correct |
| `evidence/case3b_manifest.json` | `d70d7046c3868ba6fbaf73d8f4d2a132c48feeca` | correct |
| `evidence/case3c_manifest.json` | `d70d7046c3868ba6fbaf73d8f4d2a132c48feeca` | correct |
| `evidence/case3d_manifest.json` | `d70d7046c3868ba6fbaf73d8f4d2a132c48feeca` | correct |
| `evidence/case3e_manifest.json` (sealed) | `d70d7046c3868ba6fb73f8f4d2a132c48feeca` | **39 chars — truncated** |
| `evidence/case3e_acceptance.json` | `d70d7046c3868ba6fb73f8f4d2a132c48feeca` | same truncation, copied |

## What the first erratum got wrong

`case3_gate_chain_erratum.md` (2026-08-17) inverted the error direction on
all three of its factual claims:

1. It presented the 39-character truncated value as "the canonical Case-3
   baseline." That string does not resolve to any commit in this
   repository's history.
2. It stated that `case3b/case3c/case3d_manifest.json` carry "a
   transcribed variant." They carry the canonical 40-character value.
3. It stated that `case3e_manifest.json` "carries the canonical value."
   The 3E manifest is the sole manifest carrying the truncation, and the
   3E acceptance record copied it.

The truncation was evidently introduced when the 3E manifest's gate-chain
block was written (two characters dropped), then copied into the 3E
acceptance record. The first erratum misidentified which artifacts were
affected and which value was canonical.

## Ruling

- The sealed 3E manifest and the 3E acceptance record are **not edited**:
  their SHA-256 seals bind the bytes as preregistered, and the acceptance
  authority is anchored in persisted revision/evaluation data and the
  four-authority hash (`afba877a…790ec`), not in the gate-chain labels.
- The truncated G0 is a **provenance-labeling error only**. No code, gate,
  or run consumed the manifest's gate-chain labels; every commit-level
  decision keyed on actual git history (PR #20 → `7bfbd1a` = G1;
  PR #24 → `a057982` = Q0; PR #29 → `00c1050` = Q1; PR #34 → `afa58e4`
  = Q2).
- The authoritative gate chain is `G0 = d70d7046c3868ba6fbaf73d8f4d2a132c48feeca`
  followed by G1/Q0/Q1/Q2 as above, as recorded in
  `evidence/case3_architecture_manifest.json` and here.
- `case3_gate_chain_erratum.md` is superseded by this file with respect to
  which value is canonical and which artifacts carry the error. It is left
  byte-unchanged in history.
