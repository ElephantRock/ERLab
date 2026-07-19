# P0.4A1 Closeout — Capability Ledger and Runtime Verification

## 1. Scope

**Wave:** P0.4A1 — embedding capability ledger and runtime verification
**Entry commit:** `1fea62a` (P0.4B0 closeout)
**Final executable commit:** `7980f18`

Mission: implement the capability verification layer that proves a
governed embedding operation's runtime matches its declared contract.

## 2. Governing invariant

> No governed document or query embedding operation may execute unless
> a current capability check against the actual configured provider
> proves that the resolved runtime matches the declared embedding
> contract.

## 3. Fundamental rule

> A failed or incomplete probe may create check evidence, but it may
> never create a resolved capability binding.

## 4. Commit chain

```
7980f18 test: seal P0.4A1 capability ledger architecture
c9cd043 feat: P0.4A1.8 operator verify and status commands
1cc4e93 feat: P0.4A1.6+7 encapsulated verified runtime and drift enforcement
e4bc839 feat: P0.4A1.5 check-first publication
2accec8 feat: P0.4A1.4 production-path dual probe suite
6e59cb3 feat: P0.4A1.3 check claim and lease lifecycle
3e0bb90 feat: P0.4A1.2 capability identity and fingerprint contracts
88b66b3 feat: P0.4A1.1 capability check-first schema
```

## 5. Architecture

```
EffectiveEmbeddingConfiguration
        │
        ▼
compute_runtime_config_fingerprint
        │
        ▼
create_pending_check (binding_id = NULL)
        │
        ▼
claim_check (atomic, sets lease)
        │
        ▼
probe_embedding_capability (dual_probe through adapter)
        │
        ├── pass ──► classify_resolution
        │               │
        │               ▼
        │           resolve_or_create_binding
        │               │
        │               ▼
        │           complete_check_passed (binding_id, expires_at)
        │
        └── fail ──► complete_check_failed (binding_id stays NULL)
```

## 6. Tables created

- `embedding_capability_checks` — timestamped runtime-health evidence
- `embedding_capability_bindings` — stable resolved semantic-space identity

No `embedding_profile_binding_activations` table. Activation/cutover
belongs to the next macro-wave.

## 7. Module structure

```
backend/pipeline/capability/
  __init__.py
  capability_identity.py       fingerprint, binding_id, check_id
  capability_resolution.py     classify_resolution, ResolvedBindingInput
  capability_repository.py     resolve_or_create_binding (idempotent)
  contracts.py                 lifecycle vocabulary, transitions
  capability_check_lifecycle.py  create, claim, recover, complete, cancel
  capability_probe.py          dual_probe through production adapter
  capability_check_service.py  orchestrates full check-first lifecycle
  verified_embedding_runtime.py  encapsulated authorization token
  capability_errors.py         bounded CapabilityAuthorizationError
  capability_drift.py          fingerprint match, latest-authoritative query
  capability_status.py         derived status vocabulary
```

## 8. Five-run gate

(Filled from actual results — see JSON for machine-readable evidence)

## 9. Exclusions

- No `embedding_profile_binding_activations` table
- No `vector_index_v2` production eligibility
- No binding backfill onto existing `VectorIndexRecord`
- No cutover/remediation of historical vectors
- `EmbeddingProfile.verification_status` stays `unverified`, never read for authorization

## 10. Roadmap

```
P0.4B0   CLOSED
P0.4A1   CLOSED
P0.4A2+  READY — capability-bound vector cutover
P0.5     BLOCKED pending P0.4
Frontend OPEN
```
