# P0.3.5 Legacy Reindex Closeout

> **Status:** Closeout document. P0.3.6 (physical collection quarantine) remains open.

## Regression command and totals

```bash
.venv/Scripts/python.exe -m pytest \
  backend/tests/test_pipeline/test_legacy_vector_integration.py \
  backend/tests/test_pipeline/test_legacy_vector_inventory_runtime.py \
  backend/tests/test_pipeline/test_legacy_vector_migration.py \
  backend/tests/test_pipeline/test_production_vector_isolation.py \
  backend/tests/test_pipeline/test_vector_access_enforcement.py \
  backend/tests/test_pipeline/test_scoped_vector_retrieval.py \
  backend/tests/test_pipeline/test_vector_retrieval_schema.py \
  backend/tests/test_pipeline/test_vector_indexer.py \
  backend/tests/test_pipeline/test_vector_index_registry.py \
  backend/tests/test_pipeline/test_vector_scope.py \
  backend/tests/test_pipeline/test_provenance_gating.py \
  backend/tests/test_pipeline/test_run_search_reconciliation.py \
  backend/tests/test_pipeline/test_discovery_execution_linkage.py \
  backend/tests/test_pipeline/test_execution_accounting.py \
  backend/tests/test_pipeline/test_execution_lifecycle.py \
  backend/tests/test_pipeline/test_execution_metadata.py \
  backend/tests/test_pipeline/test_search_query_executions.py \
  backend/tests/test_pipeline/test_corpus_provenance.py \
  backend/tests/test_api/test_idea_provenance.py \
  backend/tests/test_db/test_initial_migration.py
```

Expected result: **271 passed** (P0.3 canonical regression gate).

## Migration lifecycle proof

```text
✓ frozen legacy snapshot → immutable inventory records
✓ snapshot-backed exact mapping (reads legacy_identity_json, not Chroma)
✓ multi-identifier agreement (paper_id + DOI + source_id)
✓ conflict detection (paper_id vs DOI → quarantined)
✓ deterministic target planning (one per canonical paper)
✓ duplicate deduplication (3 records → 1 target → 1 indexer call)
✓ canonical content regeneration (title_abstract from Paper, not legacy doc)
✓ governed VectorIndexer with read-back verification
✓ terminal dispositions for every source record
✓ aggregate reconciliation (3 equations)
✓ source drift detection (rescan fingerprint comparison)
✓ indexer failure prevents completion
✓ already-indexed replay (zero embedding/backend calls)
✓ ownership isolation (no Paper/RunPaper/Discovery/Membership created)
✓ quarantine isolation (unmapped records have no target)
✓ target concurrency (single atomic claim)
```

## Remaining P0.3.6 work

```text
Physical deletion or archival of research_papers collection
Permanent prohibition of new explicit-legacy writes
Full-system vector isolation stress test
```
