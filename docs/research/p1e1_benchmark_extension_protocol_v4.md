# P1E.1 — Benchmark Extension Protocol, Revision 4 (inheritance authorization)

```text
status                          PROTOCOL REVISION (authorize bounded grade inheritance)
supersedes                      docs/research/p1e1_benchmark_extension_protocol_v3.md (679bc00)
preserved in history            d2e16ae (v1), 42ff0e6 (v2), 679bc00 (v3)
revision reason                 authorize preserved-v2 cal/dev grade inheritance (deviation closure)
candidate corpus                UNCHANGED
grades                          UNCHANGED (no grade/rationale changes; metadata-only binding)
```

> This revision explicitly authorizes the bounded inheritance of frozen v2
> calibration/development grades for the 180 v2-preserved candidates in the v3
> corpus. The inheritance was implemented in Commit 3 but was not preregistered;
> this revision closes that deviation by accepting inheritance under frozen
> conditions. No grades, rationales, candidates, or scores change.

## Authorization (bounded grade inheritance)

The 180 v2-preserved candidates in the v3 cal/dev corpus may carry forward their
frozen v2 grades under these conditions, all of which are proven:

```text
source records are v2 calibration/development only         yes
parent case and candidate IDs are complete                  yes (0 missing lineage)
query and candidate content hashes are unchanged            yes (180 byte-identical by hash)
candidate order is unchanged                                yes (v2-preserved candidates in original order)
carried grade equals frozen v2 grade                        yes (0 mismatches)
carried rationale is explicitly linked                      yes ("frozen v2 grade (content unchanged)")
v2 held-out records carried forward                         0
```

## Inheritance accounting

```text
inherited records                                           180
freshly adjudicated records (injected + fully-new)          264
  injected-candidate judgments                              132
  fully-new-case judgments                                  132
total                                                       444

inheritance is permitted ONLY for byte-identical v2 cal/dev content
inheritance is NOT represented as fresh adjudication
final held-out adjudication remains pending P1E.2
```

## What changes vs v3

- Inherited-v2 grade carry-forward is now explicitly authorized (was a deviation).
- All other frozen values (composition, allocation, threshold, mining scorer
  identity, custody contract, canonicalization, targets) inherited unchanged
  from v3.
- No grades, rationales, candidates, scores, or held-out content change.

## Lineage

```text
protocol v1 (preserved)   d2e16ae6b82a3fdc13854ff8032874c1ce6bd20a
protocol v2 (preserved)   42ff0e661f2acfa15ccefbd94f2770dcaa3f353d
protocol v3 (preserved)   679bc0052d0851bef48ab87663166b7a08f85bd6
protocol v4 (effective)   <full hash sealed in this commit>
```
