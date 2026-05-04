# TASK-01 Implementation Plan: TreeSearchStage Pipeline Integration

## Summary
Integrate `TreeSearchEngine` (from BATCH-62) into the pipeline as a new `TreeSearchStage` that replaces `IdeaGenerationStage` when `tree_of_thought_enabled=True`.

## Changes

### 1. `backend/pipeline/result.py` — Add `tree_data` field
- Add `tree_data: dict | None = None` to `PipelineResult`

### 2. `backend/pipeline/stages.py` — Add `TreeSearchStage` class
- New class inheriting from `PipelineStage`
- `__init__` takes `TreeSearchEngine`, `hooks`, `provider`, `kg`, `config`
- `execute()` calls `engine.search(gaps, context_papers)`
- Serializes tree into `ctx.result.tree_data`
- Enforces 500KB limit on `tree_data` (HB-03)
- `name` property returns `"idea_generation"` (same slot in STAGE_ORDER)

### 3. `backend/pipeline/orchestrator.py` — Conditional stage selection
- Import `TreeSearchStage`, `TreeSearchEngine`, `TreeSearchConfig`
- In `_build_stages()`: check `self._settings.tree_of_thought_enabled`
  - If `True`: create `TreeSearchStage` with engine + config from settings
  - If `False`: use existing `IdeaGenerationStage` (default, HB-01)

### 4. `backend/tests/test_pipeline/test_tree_search_stage.py` — 4 tests
- TEST-63-01-01: TreeSearchStage activates when flag is True
- TEST-63-01-02: IdeaGenerationStage used when flag is False
- TEST-63-01-03: tree_data populated after tree search
- TEST-63-01-04: tree_data respects 500KB limit (HB-03)

## Key Design Decisions
- `TreeSearchStage.name` returns `"idea_generation"` so it occupies the same slot in `STAGE_ORDER` — all downstream persistence/checkpoint logic works unchanged.
- 500KB limit uses `sys.getsizeof` on the JSON-serialized bytes.
- The `TreeSearchEngine` needs an `Ideator` (protocol) — we use `IdeatorAgent` which already implements the protocol.
