# P0.1 Direct-Papers Access Audit

Every site that reads the `papers` table directly, classified as either
**intentional global registry** access or **unmigrated run-corpus** access.

## Intentional global registry (8 sites)

These reads correctly access the canonical paper registry without run scoping:

| File | Line | Purpose |
|---|---|---|
| `api/routes/search.py` | 54-56 | Full-text global paper search |
| `api/routes/pipeline.py` | 1321-1323 | Citation graph lookup by source_id |
| `api/routes/pipeline.py` | 1503-1507 | Global paper stats |
| `pipeline/provenance/reference_resolver.py` | 293 | Fetch all papers for reference matching |
| `pipeline/synthesis/section_refinement.py` | 343 | Citation sanitization |
| `pipeline/synthesis/reference_validator.py` | 81-82 | DOI lookup |
| `pipeline/persistence.py` | 177 | Existence check during persist (by source_id) |
| `pipeline/persistence.py` | 388-390 | Existence check during persist (by source_id) |

## Unmigrated run-corpus access (2 sites)

These reads *intend* to be run-scoped but cannot filter by run because no FK exists:

| File | Line | Intent | Current behavior |
|---|---|---|---|
| `api/routes/gaps.py` | 353-356 | "Matched papers preview" for a gap's run | Returns global papers |
| `api/routes/gaps.py` | 415-422 | "Papers from the same pipeline run" | Returns global papers |

These should transition to `papers JOIN run_papers WHERE run_papers.run_id = ?` in P0.2.

## Needs reclassification in P0.2 (2 sites)

These may operate on a run corpus despite using canonical-paper lookups:

| File | Line | Current classification | Concern |
|---|---|---|---|
| `api/routes/evaluation.py` | 85-88 | Global | May intend run-scoped evaluation |
| `api/routes/pipeline.py` | 1277-1323 | Citation graph | Citation graph code may operate on a run corpus |

## Resolution path

- P0.2: Migrate the 2 unmigrated sites to use `run_papers` join
- P0.2: Reclassify the 2 "needs review" sites
- Global registry reads remain as-is (they are intentionally global)
