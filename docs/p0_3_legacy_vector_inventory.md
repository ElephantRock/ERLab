# P0.3.5 Legacy Vector Inventory and Reindexing

> **Status:** Production implementation complete. Closeout evidence below.
> P0.3.6 (physical collection quarantine/deletion) remains open.

## Commits comprising P0.3.5

| Commit | Description |
|---|---|
| `13d9d14` | Migration 024: inventory_runs + inventory_records |
| `d71d908` | Migration 025: reindex_targets (deduplication ledger) |
| `c056556` | Scanner, fingerprints, mapping, drift detection |
| `7b8a15c` | Production mapping, target planning, reindex, reconciliation |
| `b7b44ee` | Integrated lifecycle tests (9 tests) |
| *(this commit)* | CLI, closeout reports, cancellation/replay tests |

## Legacy collection identity

```text
Collection: research_papers
Store: chroma (PersistentClient)
Inventory module: backend/pipeline/legacy_vector_inventory.py
```

Legacy vectors and legacy documents were inventoried but were **not** copied into
governed collections or used as governed target content. Every governed replacement
was regenerated from canonical relational Paper content through the verified P0.3.2
VectorIndexer.

## Migration chain

```text
frozen legacy snapshot
→ deterministic record fingerprints
→ source snapshot fingerprint
→ snapshot-backed exact identity mapping (legacy_identity_v1 JSON)
→ multi-identifier agreement check (paper_id + DOI + source_id)
→ deterministic target planning (one per canonical paper)
→ canonical title_abstract document
→ governed VectorIndexer
→ verified vector_index_records
→ terminal dispositions for every source record
→ aggregate reconciliation
→ source fingerprint verification
```

## Mapping precedence

```text
1. Exact paper_id (must agree with DOI/source if present)
2. Exact DOI (unique match)
3. Exact source+source_record_id (unique match)
4. Exact title + first_author + publication_year (all three required)
```

Prohibited: fuzzy matching, embedding similarity, LLM adjudication, title-only, partial author.

## Identity conflicts

```text
paper_id vs DOI disagreement     → quarantined_identity_conflict
paper_id vs source_id disagreement → quarantined_identity_conflict
multiple DOI matches              → quarantined_ambiguous
multiple source_id matches        → quarantined_ambiguous
```

## Operator CLI

```text
erlab vectors inventory-legacy --target-profile <id> [--dry-run] [--execute]
erlab vectors reindex-legacy --inventory-run-id <id>
erlab vectors resume-legacy --inventory-run-id <id>
erlab vectors verify-legacy --inventory-run-id <id>
erlab vectors report-legacy --inventory-run-id <id> [--format json|text]
```

## P0.4 limitation

The target embedding profile has `verification_status = unverified`. P0.3.5 proves
deterministic migration and governed backend verification, not actual model resolution
or semantic embedding quality. P0.4 owns that capability handshake.

## Legacy collection retention

The `research_papers` collection remains physically present. Governed retrieval cannot
access it. Physical deletion or archival is deferred to P0.3.6.
