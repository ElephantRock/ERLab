# Release-Readiness Audit — v1.0.0

## 1. Repository governance

```text
Branch protection:     NOT APPLICABLE — private repo on free plan,
                       requires GitHub Pro for branch protection rules
Default branch:        main (set)
CI run on 3ed9851:     FAILED — pre-existing lint debt (ruff 4427 errors),
                       tests did not execute because lint is a CI gate
Obsolete branches:     feat/quarantine-and-frontend-redesign (identical to main),
                       master (alpha v0.2.0) — both still present
```

**Finding: BLOCKER** — CI does not pass on the release commit. The lint step
fails before tests run. The CI workflow gates on `ruff check` which reports
4,427 errors across the codebase. Local `pytest -m "not slow and not integration"`
passes (5,033) because it does not run ruff, but CI does.

## 2. Git history secret audit

```text
Tool:                  gitleaks (972 commits scanned)
Total findings:        20

curl-auth-header:      2 (documentation examples in docs/endpoints/auth.md)
generic-api-key:       8 (test fixtures: sk-1234..., AIzaSyB123abc..., api_key=sk-abc123...)
jwt:                   10 (sessions/ directory — session logs contain JWT tokens)
```

**Finding: BLOCKER for public release** — The `sessions/` directory (10 findings)
contains JWT tokens in session log files from prior development work. These are
in the git history (not just working tree) and cannot be trivially removed
without rewriting history.

The 8 generic-api-key findings are test fixtures using obvious placeholder
values (`sk-1234567890abcdefghijklmnopqrstuv`, `AIzaSyB123abc`). These are
not real secrets.

The 2 curl-auth-header findings are example JWTs in documentation.

**Recommendation:** Do not make the repository public until the `sessions/`
directory is audited or history is sanitized. The private canonical repository
with full history should be retained; a sanitized public mirror should be
created from v1.0.0 if public release is desired.

## 3. Architecture truthfulness audit

### Verified claims

- The typed claim composer (`typed_claim_composer.py`) uses semantic slots
  and validates provider output — CONFIRMED in code and tests
- `build_deterministic_components()` generates title, methods, results,
  and conclusion from spec — CONFIRMED
- `validate_provider_output()` rejects [RESULT-N] markers — CONFIRMED
- `evaluate_paper_gates()` is side-effect-free (no DB writes, no provider
  calls) — CONFIRMED via source inspection
- `claim_alignment.py` detects unexecuted methods in title/abstract/conclusion
  — CONFIRMED
- `claim_result_validator.py` checks marker roles match claims — CONFIRMED
- LLM cannot generate RESULT markers (provider output sanitized before
  assembly) — CONFIRMED

### Documentation corrections needed

- **ARCHITECTURE.md** lists `paper_gate_evaluator.py` — correct, exists
- **ARCHITECTURE.md** lists `revision_directive.py` — correct, exists
- **README.md** says "v1.0.0" and "stable" — should clarify this is an
  engineering/research release, not validated autonomous science

## 4. Evidence-chain integrity

### Verified chain

```
ExperimentSpec (frozen JSON with SHA-256)
→ execute_experiment() (checked-in script, code hash verified)
→ metrics.json (scalar values only)
→ ExperimentManifest (dataset, split, analysis, artifacts)
→ ResultMarker (marker, metric, value, direction, role)
→ paper_meta_json (result_markers array with all semantics)
→ PaperRevision table (revision history with parent linkage)
```

### Potential drop points

1. **ExperimentResult rows are sometimes ephemeral** — the Phase 14 RF run
   used `execute_experiment()` directly without persisting to DB. This is
   a test-path issue; the pipeline stage does persist.

2. **ResultMarker.direction and .role default to empty string** — Phase 7
   markers (persisted before Phase 8/9) have no direction/role. The evaluator
   handles this by treating empty direction as "neutral" (no comparison).

3. **paper_recovery.py overwrites paper_md in place** — the Phase 7H fix
   added PaperRevision storage before overwrite, but legacy proposals from
   Phase 5-7 may have been overwritten without revision records.

## 5. Migration correctness

```text
Alembic version:       035 (paper_revisions)
Fresh DB upgrade:      PASS (verified in Phase 9D)
ORM agreement:         PaperRevision model matches migration 035
Rollback:              Not provided (append-only table, no downgrade needed)
```

**Verified claim** — migration 035 creates the table correctly on both
existing and fresh databases.

## 6. Security boundaries

### Verified

- `resolve_entrypoint_securely()` rejects absolute paths, `..` traversal,
  symlink escape, and code-hash mismatch — CONFIRMED
- Provider output is sanitized (achievement claims stripped, RESULT markers
  rejected) before paper assembly — CONFIRMED
- `.env` files are gitignored — CONFIRMED
- No secrets in tracked files (gitleaks test fixtures are placeholders) — CONFIRMED

### Improvement

- The `sessions/` directory in git history contains JWT tokens — BLOCKER
  for public release
- API key authentication (`verify_api_key`) is disabled when no key is set
  — acceptable for development but should be documented
- Diagnostics endpoints are registered without auth — acceptable for dev
  but should be gated in production

## 7. Reproducibility

### Verified

- Experiment scripts are checked-in and SHA-256 hashed
- Datasets have hash verification in dataset_meta.json
- Seeds are frozen (42) and splits are deterministic
- All metrics reproduce with diff=0.00000000

### Unverified

- Clean-clone test not yet performed (item 4 in this audit)
- Dependency pinning via `uv.lock` exists but lockfile compatibility
  with `pip install` workflow not verified on CI

## 8. Documentation consistency

### Corrections needed

1. **README.md** version badge says "stable" — should say "research/engineering release"
2. **README.md** does not mention the distinction between computational review (GPT-5.3) and human peer review
3. **REPRODUCIBILITY.md** does not note that datasets are NOT in the repository (gitignored) — users need the UCI downloads
4. **ARCHITECTURE.md** should note that CI currently fails on lint

## Audit ledger

```text
BLOCKERS:
  1. CI fails on lint (4,427 ruff errors) — tests don't execute on GitHub Actions
  2. sessions/ directory contains JWT tokens in git history — not safe for public release

IMPROVEMENTS:
  1. Delete obsolete branches (feat/quarantine-and-frontend-redesign, master)
  2. Fix ruff lint errors to enable CI
  3. Sanitize or exclude sessions/ from history before public release
  4. Gate diagnostics endpoints in production
  5. Document dataset availability (UCI downloads required)

DOCUMENTATION CORRECTIONS:
  1. README: "stable" → "research/engineering release"
  2. README: add computational-vs-human-review distinction
  3. REPRODUCIBILITY: note datasets are not in repository
  4. ARCHITECTURE: note CI lint status

VERIFIED CLAIMS:
  - Typed claim composition prevents LLM from generating RESULT markers
  - Deterministic renderers produce correct titles, results, and conclusions
  - Gate evaluator is side-effect-free
  - Experiments reproduce exactly (diff=0.0)
  - Migration 035 works on fresh and existing databases
  - Entry-point resolution is security-validated
  - Evidence chain persists across restart

UNVERIFIED CLAIMS:
  - Clean-clone install + test (not yet performed)
  - CI green on main (blocked by lint)
  - Public release readiness (sessions/ history)
```
