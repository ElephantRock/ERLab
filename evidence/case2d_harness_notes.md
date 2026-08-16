# Case 2D Harness Notes — Provenance Repair + Known Limitation

## Provenance repair (this change)

The owner's PR #13 review found the committed `case2d_manifest.json`
hashing to `0e94174b…` while the seal says `679bc0fd…` (P1: broken
pre-registration integrity link). Root cause: the pre-launch manifest
was written by Python on Windows (CRLF line endings, 3634 bytes); git's
`autocrlf` normalization stripped the 53 carriage returns on commit
(LF, 3581 bytes). The seal hashed the original bytes.

No new seal was manufactured. The repair is byte recovery:

- **2D**: the exact pre-launch bytes were still present, untouched, in
  the working tree (hash verified `679bc0fd…`). Committed byte-exact.
- **2B / 2C**: same normalization defect found in the same review pass
  (owner flagged 2D; 2B/2C discovered during repair). The originals
  were deterministically reconstructed — LF→CRLF restoration — and the
  reconstruction is proven correct because it hashes to the
  **pre-existing** seals (`34125da5…`, `35687d0d…`). Committed
  byte-exact.
- **2A**: committed bytes already matched its seal; restored to the
  sealed bytes after an intermediate staging error.

`.gitattributes` now marks the sealed evidence files `-text` so they
round-trip byte-for-byte on every platform. All four staged manifests
verified to hash to their seals before commit, and re-verified against
the committed blobs after.

## Known harness limitation (preserved as-is, not rewritten)

The executed harness (`evidence/launch_case2d.py`, sealed sha256
`31bd2ff5…`, committed bytes verified identical) checks
`auto_design_status == "designed"` after the orchestrator returns but
does **not** explicitly reject a non-`SUCCEEDED` orchestrator outcome
before continuing. This does not affect the 2D run of record: its
recorded outcome was `succeeded` (`case2d_result.json`,
`run_20260815_231659`). The executed harness is preserved unmodified
so the run's provenance stays intact; the limitation is recorded here
for any successor harness (e.g., Case 3), which should fail closed on
non-`SUCCEEDED` outcomes.

## Comparison-file omission (this change)

The 2D-finalized `case2_comparison.json` (Decision = "ACCEPTED via
2D…", 2D hash and intervention rows updated) was edited after the run
but omitted from the finalize commit's `git add` list; the branch
carried the stale "2D pending" version. The finalized version is
committed here. Content-only omission; no data was lost.

## Review-findings adjudication (PR closeout, 2026-08-16)

The automated review gate flagged four findings on the closeout PR.
Adjudicated against the repository trees:

1. **HIGH "Ghost evidence: failure to unlink 2D stale files" — false
   positive.** `git diff --name-status main <delivery>` lists 14 files:
   4 modified, 10 added, **zero deletions**; and the set of files on
   `main` absent from the delivery is empty. No stale 2D file exists;
   there is nothing to unlink. The delivery tree is byte-identical to
   the verified stack tip (`git diff --stat` between them is empty).
2. **MEDIUM "`case2a_manifest.json` missing from byte-freeze" — false
   positive.** No such file exists. Attempt 2A's manifest is
   `evidence/case2_manifest.json`, which IS listed with `-text` and
   whose committed blob equals its seal (`4a161e0a…`, verified).
3. **MEDIUM "SQL injection in launch_case2d.py" — theoretical.** The
   interpolated values are integer IDs from the process's own prior
   SELECT on its private SQLite file; no user-controlled input reaches
   the query. The harness is a sealed historical artifact (owner
   instruction: preserved as-is, sha256 `31bd2ff5…`); the pattern is
   noted for successor harnesses, which should use parameterized
   queries.
4. **MEDIUM "hardcoded relative paths" — intentional.** The harness is
   repository-root-relative by design (it is executed from the repo
   root, like every Case-1/Case-2 launcher); noted for successor
   harnesses.
