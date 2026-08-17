# Case 3 Pre-Registration Protocol Note

Adjudication of an automated-review P1 against the frozen protocol.
This is a repository note, not a new acceptance gate.

## The finding

A review finding asked that the Case-3 qualification require a
pre-registration Git ancestor: a commit, in Git history before launch,
containing the manifest and harness. The Case-3 runs do not have one.

## Why that is not a contract failure

The frozen C3-0/C3-4 protocol never required Git ancestry for
pre-registration. What it required — and what was done — was:

1. The manifest and harness were byte-sealed **before launch** via
   SHA-256 (`evidence/case3_manifest.sha256` =
   `9c8644ff…` for the manifest; harness sha256 `d6d300c1…` recorded
   inside the manifest and re-verified at C3-5 preflight).
2. The run executed at **exactly** the frozen qualification SHA
   `Q0 = a057982…` with a clean tracked tree; the sealed protocol
   files rode along as untracked artifacts precisely so that the
   production tree would not move past Q0 before the run.
3. The C3-5 hard preflight verified both seals against the on-disk
   bytes before launch (`evidence/case3_preflight.json`:
   `manifest_seal` and `harness_seal` gates, both PASS).

Committing the protocol files before launch would have required
either a new commit on top of Q0 (breaking "run at exactly Q0 with a
clean tree") or a detached-branch ceremony the contract never asked
for. The seal-plus-preflight design is the pre-registration the
contract specified; byte hashes bind content, Git ancestry binds
history, and the contract bound content.

## Follow-up hygiene (non-binding)

For future qualification attempts, a companion branch containing the
sealed artifacts can be pushed before launch so reviewers see the
pre-registration in Git without the run tree leaving Q0. This is
convenience for review, not an acceptance criterion, and was not one
for Case 3.
