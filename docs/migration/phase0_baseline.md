# Phase 0 Baseline Report

**Date:** 2026-06-16
**Destination:** `C:\Next-Era\Elephant-Rock-Research-Lab`
**Git history:** Preserved (20+ commits, latest: `c275c6d`)
**Phase 0 commit:** `e2c0171`

## Migration Verification

| Item | Status |
|------|--------|
| Source code (backend/) | ✅ Copied with working-tree changes |
| Frontend (frontend/) | ✅ Copied with working-tree changes |
| Migrations (alembic/) | ✅ Copied |
| Scripts, configs, docs | ✅ Copied |
| Lockfiles (uv.lock) | ✅ Copied |
| .env / .env.docker | ✅ Excluded |
| data/ / sessions/ / logs/ | ✅ Excluded |
| .venv / node_modules | ✅ Excluded |
| .coverage / caches | ✅ Excluded |
| Design drafts (AIV, SOUL, STATE, etc.) | ✅ Excluded |
| .gitignore updated | ✅ Comprehensive exclusions |
| New source files (14) | ✅ Included |
| Old orchestrator.py monolith | ✅ Removed (replaced by package) |

## Tooling Baseline

| Check | Result |
|-------|--------|
| `uv sync` | ✅ 160 packages installed |
| `uv sync --extra dev` | ✅ 14 dev packages (ruff, pytest, mypy, etc.) |
| `ruff check .` | ⚠️ 2,304 errors (1,432 auto-fixable) — existing tech debt, deferred |
| `pytest --co -q` | ✅ 3,299 tests collected |
| `pytest -q --tb=no` | **63 failed, 3216 passed, 20 skipped** (88s) |

## Test Failure Categories (63 total)

### 1. bcrypt password >72 bytes (8 failures)
Tests: `test_batch28_auth.py` (8 tests)
Root cause: bcrypt library enforces 72-byte password limit. Test passwords exceed it.
Fix scope: Reduce test password lengths. Not architectural.

### 2. Hardcoded old project path (4 failures)
Tests: `test_batch107_frontend.py` (4 dark mode tests)
Root cause: Tests reference `C:\Next-Era\elephant-rock-platform\frontend\src\hooks\useDarkMode.ts` — hardcoded absolute path to old project + deleted file.
Fix scope: Update test to use relative paths / check for new path.

### 3. Removed SOUL.md (3 failures)
Tests: `test_batch83_soul_errors.py` (3 tests)
Root cause: SOUL.md intentionally excluded from clean migration.
Fix scope: Remove these tests or mark as obsolete.

### 4. Removed data/ fixtures (7 failures)
Tests: `test_grounding_scorer.py` (6), `test_runner.py` (1)
Root cause: Corpus data files (`data/model_certification/eval_cases/`, `data/model_certification/candidates/`) removed as runtime artifacts.
Fix scope: Decide whether to regenerate fixtures or adjust tests.

### 5. LM Studio integration (12 failures)
Tests: `test_enforcement_integration.py` (5), `test_phase2_enforcement.py` (5), `test_staged_enforcement.py` (2)
Root cause: Tests require LM Studio running and model certification data. Various assertion failures around routing, enforcement, repair.
Fix scope: Mark as integration tests requiring external service. Not architectural.

### 6. DB schema / migration (5 failures)
Tests: `test_batch55_task01.py` (3), `test_initial_migration.py` (1), `test_batch14_task01.py` (1), `test_batch38_task01.py` (1)
Root cause: SQLite schema issues — `no such column: pipeline_runs.run_id_str`, `no such table: ideas`.
Fix scope: Migration setup issue in test environment. Not architectural.

### 7. Docker/env config (4 failures)
Tests: `test_batch30_docker.py` (2), `test_batch151_docker_badge.py` (1), `test_batch137_no_hardcoded_ips.py` (1)
Root cause: `.env.docker` removed, docker-compose changes from working tree, hardcoded IP detection.
Fix scope: Regenerate `.env.docker` template or update test expectations.

### 8. WeasyPrint native library (1 failure)
Tests: `test_33_01_01_export_pdf_returns_pdf_content`
Root cause: `libgobject-2.0-0` not available on Windows.
Fix scope: Platform issue. Skip on Windows.

### 9. Working-tree code changes (10 failures)
Tests: `test_batch184_orchestrator_yaml.py` (3 — stage count 17 ≠ 6/16), `test_batch153/174_paper_synthesis` (2), `test_batch174_core_stages` (1), `test_batch121_claim_extraction` (1), `test_batch109_verification` (1), `test_knowledge_ingest.py` (1), `test_cli/test_dev.py` (1)
Root cause: Uncommitted source changes altered behavior (stage counts, metadata handling, empty results, etc.).
Fix scope: Tests need updating to match new behavior. Some may reveal real regressions.

### 10. CLI setup tests (3 failures)
Tests: `test_cli/test_setup.py` (2), `test_cli/test_dev.py` (1)
Root cause: CLI exit code assertions failing.
Fix scope: Investigate CLI behavior changes.

### 11. Other (6 failures)
Tests: `test_experiment_api.py` (1), `test_db/test_batch38_task01.py` (1)
Root cause: Various. Need individual triage.

## Conclusion

Baseline established. 3216/3299 tests pass (97.5%). The 63 failures break down into:
- **Environmental** (bcrypt, WeasyPrint, LM Studio, DB): ~26 — fix infrastructure, not code
- **Migration artifacts** (removed SOUL.md, removed data/, hardcoded paths): ~14 — update tests
- **Working-tree changes** (stage counts, behavior changes): ~10 — update tests or investigate
- **Config** (docker, .env.docker): ~4 — regenerate templates
- **Other**: ~9 — individual triage needed

**Phase 0 is complete.** No refactor work should begin on failing tests until the architectural phases introduce the new contracts.
